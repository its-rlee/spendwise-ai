import 'dart:async';
import 'dart:convert';

import 'dart:typed_data';

import 'document_models.dart';

import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

class ApiException implements Exception {
  final int statusCode;
  final String message;

  ApiException(this.statusCode, this.message);

  @override
  String toString() => message;
}

class TransactionRecord {
  final int id;
  final String merchant;
  final String amount;
  final String category;
  final String currency;
  final String direction;
  final String? date;

  TransactionRecord({
    required this.id,
    required this.merchant,
    required this.amount,
    required this.category,
    required this.currency,
    required this.direction,
    required this.date,
  });

  factory TransactionRecord.fromJson(Map<String, dynamic> json) {
    return TransactionRecord(
      id: json['id'] as int,
      merchant: json['merchant'].toString(),
      amount: json['amount'].toString(),
      category: json['category'].toString(),
      currency: json['currency'].toString(),
      direction: json['direction']?.toString() ?? 'debit',
      date: json['transaction_date']?.toString(),
    );
  }
}

class AssistantReply {
  final String answer;
  final Map<String, dynamic> facts;

  AssistantReply({required this.answer, required this.facts});

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    return AssistantReply(
      answer: json['answer'] as String,
      facts: Map<String, dynamic>.from(json['facts'] as Map),
    );
  }
}

class SpendwiseApi {
  final http.Client _client;
  final Future<String> Function() _tokenProvider;
  final String baseUrl;

  SpendwiseApi({
    http.Client? client,
    Future<String> Function()? tokenProvider,
    String? baseUrl,
  }) : _client = client ?? http.Client(),
       _tokenProvider = tokenProvider ?? _supabaseToken,
       baseUrl =
           baseUrl ??
           const String.fromEnvironment(
             'API_BASE_URL',
             defaultValue: 'http://127.0.0.1:8000',
           );

  void checkResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return;
    }

    String message = 'Request failed';

    try {
      final body = jsonDecode(response.body);

      if (body is Map) {
        final detail = body['detail'];

        if (detail is String) {
          message = detail;
        } else if (detail is Map && detail['message'] is String) {
          message = detail['message'] as String;
        }
      }
    } catch (_) {
      // Avoid displaying raw server output.
    }

    throw ApiException(response.statusCode, message);
  }

  static Future<String> _supabaseToken() async {
    final auth = Supabase.instance.client.auth;
    var session = auth.currentSession;

    if (session == null) {
      throw ApiException(401, 'Please sign in.');
    }

    if (session.isExpired) {
      try {
        session = (await auth.refreshSession()).session;
      } catch (_) {
        throw ApiException(401, 'Session expired. Please sign in again.');
      }
    }

    if (session == null) {
      throw ApiException(401, 'Please sign in again.');
    }

    return session.accessToken;
  }

  Future<dynamic> _request(String path, {Map<String, dynamic>? body}) async {
    final token = await _tokenProvider();

    final headers = {
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    };

    final uri = Uri.parse('$baseUrl$path');

    late http.Response response;

    try {
      if (body == null) {
        response = await _client
            .get(uri, headers: headers)
            .timeout(const Duration(seconds: 30));
      } else {
        response = await _client
            .post(uri, headers: headers, body: jsonEncode(body))
            .timeout(const Duration(seconds: 150));
      }
    } on TimeoutException {
      throw ApiException(0, 'API request timed out.');
    } on http.ClientException {
      throw ApiException(0, 'Cannot connect to FastAPI.');
    }

    checkResponse(response);

    try {
      return jsonDecode(response.body);
    } on FormatException {
      throw ApiException(0, 'Server returned invalid JSON.');
    }
  }

  Future<List<TransactionRecord>> getTransactions() async {
    final result = await _request('/api/v1/transactions');

    if (result is! List) {
      throw ApiException(0, 'Invalid transaction response.');
    }

    return result.map((item) {
      return TransactionRecord.fromJson(Map<String, dynamic>.from(item as Map));
    }).toList();
  }

  Future<AssistantReply> askAssistant(String question) async {
    final result = await _request(
      '/api/v1/assistant/ask',
      body: {'question': question},
    );

    return AssistantReply.fromJson(Map<String, dynamic>.from(result as Map));
  }

  static const maxDocumentBytes = 5 * 1024 * 1024;

  Future<UploadedDocument> uploadDocument({
    required String filename,
    required Uint8List bytes,
  }) async {
    if (bytes.isEmpty || bytes.length > maxDocumentBytes) {
      throw ApiException(413, 'Choose a nonempty file under 5 MB.');
    }

    final extension = filename.split('.').last.toLowerCase();

    final String path;

    if (extension == 'pdf') {
      path = '/api/v1/documents/upload';
    } else if (['jpg', 'jpeg', 'png'].contains(extension)) {
      path = '/api/v1/receipts/upload';
    } else {
      throw ApiException(415, 'Only PDF, JPG and PNG are supported.');
    }

    final token = await _tokenProvider();

    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl$path'));

    request.headers['Authorization'] = 'Bearer $token';

    request.files.add(
      http.MultipartFile.fromBytes('file', bytes, filename: filename),
    );

    try {
      final streamedResponse = await _client
          .send(request)
          .timeout(const Duration(seconds: 90));

      final response = await http.Response.fromStream(streamedResponse);

      checkResponse(response);

      return UploadedDocument.fromJson(
        Map<String, dynamic>.from(jsonDecode(response.body) as Map),
      );
    } on TimeoutException {
      throw ApiException(0, 'Upload timed out.');
    } on http.ClientException {
      throw ApiException(0, 'Could not connect to FastAPI.');
    }
  }

  Future<List<TransactionDraftRecord>> prepareDocument(
    String documentId,
  ) async {
    final result = await _request(
      '/api/v1/documents/$documentId/prepare',
      body: <String, dynamic>{},
    );

    return (result as List).map((item) {
      return TransactionDraftRecord.fromJson(
        Map<String, dynamic>.from(item as Map),
      );
    }).toList();
  }

  Future<List<TransactionDraftRecord>> getDrafts(String documentId) async {
    final result = await _request('/api/v1/documents/$documentId/drafts');

    return (result as List).map((item) {
      return TransactionDraftRecord.fromJson(
        Map<String, dynamic>.from(item as Map),
      );
    }).toList();
  }

  Future<void> approveDraft(
    String draftId,
    Map<String, dynamic> corrected, {
    bool confirmSimilar = false,
    bool confirmItemMismatch = false,
  }) async {
    await _request(
      '/api/v1/drafts/$draftId/approve',
      body: {
        ...corrected,
        'confirm_similar': confirmSimilar,
        'confirm_item_mismatch': confirmItemMismatch,
      },
    );
  }

  Future<void> rejectDraft(String draftId, String reason) async {
    await _request('/api/v1/drafts/$draftId/reject', body: {'reason': reason});
  }

  void dispose() {
    _client.close();
  }

  Future<void> saveDraftItems(
    String draftId,
    List<Map<String, dynamic>> items,
  ) async {
    final token = await _tokenProvider();

    final response = await _client
        .patch(
          Uri.parse('$baseUrl/api/v1/drafts/$draftId/items'),
          headers: {
            'Authorization': 'Bearer $token',
            'Content-Type': 'application/json',
          },
          body: jsonEncode({'items': items}),
        )
        .timeout(const Duration(seconds: 30));

    checkResponse(response);
  }
}
