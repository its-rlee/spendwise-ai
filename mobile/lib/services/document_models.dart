class UploadedDocument {
  final String id;
  final String filename;
  final String status;

  UploadedDocument({
    required this.id,
    required this.filename,
    required this.status,
  });

  factory UploadedDocument.fromJson(Map<String, dynamic> json) {
    return UploadedDocument(
      id: json['document_id'] as String,
      filename: json['filename'] as String,
      status: json['status'] as String,
    );
  }
}

class TransactionDraftRecord {
  final String id;
  final String documentId;
  final int sourceIndex;

  final String? merchant;
  final String? amount;
  final String? direction;
  final String? transactionDate;
  final String? currency;

  final String status;
  final List<String> reviewReasons;

  TransactionDraftRecord({
    required this.id,
    required this.documentId,
    required this.sourceIndex,
    required this.merchant,
    required this.amount,
    required this.direction,
    required this.transactionDate,
    required this.currency,
    required this.status,
    required this.reviewReasons,
  });

  factory TransactionDraftRecord.fromJson(Map<String, dynamic> json) {
    return TransactionDraftRecord(
      id: json['id'] as String,
      documentId: json['document_id'] as String,
      sourceIndex: json['source_index'] as int,
      merchant: json['merchant']?.toString(),
      amount: json['amount']?.toString(),
      direction: json['direction']?.toString(),
      transactionDate: json['transaction_date']?.toString(),
      currency: json['currency']?.toString(),
      status: json['status'] as String,
      reviewReasons: List<String>.from(json['review_reasons'] ?? []),
    );
  }
}
