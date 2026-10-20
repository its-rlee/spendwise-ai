import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:mobile/services/spendwise_api.dart';

void main() {
  test('GET transactions attaches Bearer token', () async {
    final client = MockClient((request) async {
      expect(request.headers['Authorization'], 'Bearer fake-test-token');

      expect(request.url.path, '/api/v1/transactions');

      return http.Response(
        jsonEncode([
          {
            'id': 1,
            'merchant': 'Walmart',
            'amount': '45.50',
            'category': 'Groceries',
            'currency': 'USD',
            'direction': 'debit',
            'transaction_date': '2026-10-19',
          },
        ]),
        200,
      );
    });

    final api = SpendwiseApi(
      client: client,
      tokenProvider: () async => 'fake-test-token',
      baseUrl: 'http://localhost:8000',
    );

    final records = await api.getTransactions();

    expect(records.length, 1);
    expect(records.first.merchant, 'Walmart');
    expect(records.first.amount, '45.50');

    api.dispose();
  });

  test('Assistant sends a question to FastAPI', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/api/v1/assistant/ask');

      final body = jsonDecode(request.body);
      expect(body['question'], 'Groceries this month?');

      return http.Response(
        jsonEncode({
          'answer': 'You spent \$125.75 USD.',
          'facts': {
            'currency': 'USD',
            'total': '125.75',
            'transaction_count': 2,
          },
        }),
        200,
      );
    });

    final api = SpendwiseApi(
      client: client,
      tokenProvider: () async => 'fake-test-token',
      baseUrl: 'http://localhost:8000',
    );

    final reply = await api.askAssistant('Groceries this month?');

    expect(reply.facts['total'], '125.75');
    expect(reply.facts['transaction_count'], 2);

    api.dispose();
  });

  test('Unauthorized request throws ApiException', () async {
    final client = MockClient((request) async {
      return http.Response('Unauthorized', 401);
    });

    final api = SpendwiseApi(
      client: client,
      tokenProvider: () async => 'fake-test-token',
      baseUrl: 'http://localhost:8000',
    );

    await expectLater(
      api.getTransactions(),
      throwsA(
        isA<ApiException>().having(
          (error) => error.statusCode,
          'statusCode',
          401,
        ),
      ),
    );

    api.dispose();
  });
}
