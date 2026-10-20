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

  final List<ReceiptItemDraft> receiptItems;
  final bool itemsReviewed;
  final String? receiptSubtotal;

  TransactionDraftRecord({
    required this.id,
    required this.documentId,
    required this.sourceIndex,
    required this.merchant,
    required this.receiptItems,
    required this.itemsReviewed,
    required this.receiptSubtotal,
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
      receiptItems: ((json['receipt_items'] ?? []) as List)
          .map(
            (item) => ReceiptItemDraft.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      itemsReviewed: json['items_reviewed'] == true,
      receiptSubtotal: json['receipt_subtotal']?.toString(),
      amount: json['amount']?.toString(),
      direction: json['direction']?.toString(),
      transactionDate: json['transaction_date']?.toString(),
      currency: json['currency']?.toString(),
      status: json['status'] as String,
      reviewReasons: List<String>.from(json['review_reasons'] ?? []),
    );
  }
}

class ReceiptItemDraft {
  final String name;
  final String? amount;
  final String category;

  ReceiptItemDraft({
    required this.name,
    required this.amount,
    required this.category,
  });

  factory ReceiptItemDraft.fromJson(Map<String, dynamic> json) {
    return ReceiptItemDraft(
      name: json['name']?.toString() ?? '',
      amount: json['amount']?.toString(),
      category: json['category']?.toString() ?? 'Uncategorized',
    );
  }
}
