import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:mobile/services/spendwise_api.dart';

void main() {
  SpendwiseApi makeApi(MockClient client) {
    return SpendwiseApi(
      client: client,
      tokenProvider: () async => 'fake-test-token',
      baseUrl: 'http://localhost:8000',
    );
  }

  test('PDF upload uses authenticated multipart', () async {
    final client = MockClient((request) async {
      expect(request.method, 'POST');

      expect(request.url.path, '/api/v1/documents/upload');

      final authorization = request.headers.entries
          .firstWhere((entry) => entry.key.toLowerCase() == 'authorization')
          .value;

      expect(authorization, 'Bearer fake-test-token');

      final contentType = request.headers.entries
          .firstWhere((entry) => entry.key.toLowerCase() == 'content-type')
          .value;

      expect(contentType, contains('multipart/form-data'));
      expect(utf8.decode(request.bodyBytes), contains('name="file"'));

      return http.Response(
        jsonEncode({
          'document_id': 'doc-123',
          'filename': 'sample.pdf',
          'status': 'text_ready',
        }),
        201,
      );
    });

    final api = makeApi(client);

    final result = await api.uploadDocument(
      filename: 'sample.pdf',
      bytes: Uint8List.fromList(utf8.encode('%PDF-1.4\nSYNTHETIC TEST')),
    );

    expect(result.id, 'doc-123');
    expect(result.status, 'text_ready');

    api.dispose();
  });

  test('Prepare document returns drafts', () async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/documents/doc-123/prepare');

      return http.Response(
        jsonEncode([
          {
            'id': 'draft-1',
            'document_id': 'doc-123',
            'source_index': 0,
            'merchant': 'TEST STORE',
            'amount': '9.19',
            'direction': 'debit',
            'transaction_date': '2026-10-19',
            'currency': null,
            'review_reasons': ['Currency requires review'],
            'status': 'pending',
          },
        ]),
        201,
      );
    });

    final api = makeApi(client);
    final drafts = await api.prepareDocument('doc-123');

    expect(drafts.length, 1);
    expect(drafts.first.amount, '9.19');
    expect(drafts.first.currency, isNull);
    expect(drafts.first.status, 'pending');

    api.dispose();
  });

  test('Approval includes corrected fields', () async {
    final client = MockClient((request) async {
      expect(request.url.path, '/api/v1/drafts/draft-1/approve');

      final data = jsonDecode(request.body);

      expect(data['amount'], '9.19');
      expect(data['currency'], 'USD');
      expect(data['confirm_similar'], false);

      return http.Response('{"transaction_id":42,"status":"approved"}', 201);
    });

    final api = makeApi(client);

    await api.approveDraft('draft-1', {
      'merchant': 'TEST STORE',
      'amount': '9.19',
      'currency': 'USD',
      'transaction_date': '2026-10-19',
      'direction': 'debit',
      'category': 'Groceries',
    });

    api.dispose();
  });

  test('Duplicate warning is preserved', () async {
    final client = MockClient((request) async {
      return http.Response(
        jsonEncode({
          'detail': {
            'message': 'Possible duplicate transaction',
            'existing_transaction_id': 42,
          },
        }),
        409,
      );
    });

    final api = makeApi(client);

    await expectLater(
      api.approveDraft('draft-1', {
        'merchant': 'TEST STORE',
        'amount': '9.19',
        'currency': 'USD',
        'transaction_date': '2026-10-19',
        'direction': 'debit',
        'category': 'Groceries',
      }),
      throwsA(
        isA<ApiException>().having((e) => e.statusCode, 'statusCode', 409),
      ),
    );

    api.dispose();
  });

  test('Oversized file is blocked locally', () async {
    final client = MockClient((request) async {
      fail('HTTP request must not be sent');
    });

    final api = makeApi(client);

    await expectLater(
      api.uploadDocument(
        filename: 'large.pdf',
        bytes: Uint8List(SpendwiseApi.maxDocumentBytes + 1),
      ),
      throwsA(isA<ApiException>()),
    );

    api.dispose();
  });
}
