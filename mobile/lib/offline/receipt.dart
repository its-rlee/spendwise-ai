import 'dart:convert';

// Money stays in integer minor units; this first version supports two-decimal currencies.
int? parseMoney(String value) {
  final input = value.trim().replaceAll(RegExp(r'[\$€£\s]'), '');
  if (!RegExp(r'^-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?$').hasMatch(input)) {
    return null;
  }
  final normalized = input.replaceAll(',', '');
  final negative = normalized.startsWith('-');
  final parts = normalized.replaceFirst('-', '').split('.');
  final whole = int.tryParse(parts[0]);
  if (whole == null || whole > 999999999) return null;
  final cents =
      whole * 100 +
      (parts.length == 2 ? int.parse(parts[1].padRight(2, '0')) : 0);
  return negative ? -cents : cents;
}

String money(int? cents) => cents == null
    ? ''
    : '${cents < 0 ? '-' : ''}${cents.abs() ~/ 100}.${(cents.abs() % 100).toString().padLeft(2, '0')}';

class ReceiptItem {
  String description;
  String rawDescription;
  int? amount;
  double? quantity;
  int? unitPrice;
  ReceiptItem({
    required this.description,
    this.rawDescription = '',
    this.amount,
    this.quantity,
    this.unitPrice,
  });
  Map<String, dynamic> toJson() => {
    'description': description,
    'rawDescription': rawDescription,
    'amount': amount,
    'quantity': quantity,
    'unitPrice': unitPrice,
  };
  factory ReceiptItem.fromJson(Map<String, dynamic> json) => ReceiptItem(
    description: json['description'] as String,
    rawDescription: json['rawDescription'] as String? ?? '',
    amount: json['amount'] as int?,
    quantity: (json['quantity'] as num?)?.toDouble(),
    unitPrice: json['unitPrice'] as int?,
  );
}

class Receipt {
  final String id;
  final String createdAt;
  String merchant;
  String? date;
  String currency;
  int? subtotal;
  int? tax;
  int? total;
  int? tip;
  int? fees;
  int? discount;
  String category;
  bool reviewed;
  final String rawText;
  final String? imageName;
  final List<ReceiptItem> items;
  Receipt({
    required this.id,
    required this.createdAt,
    this.merchant = '',
    this.date,
    this.currency = '',
    this.subtotal,
    this.tax,
    this.total,
    this.tip,
    this.fees,
    this.discount,
    this.category = 'Other',
    this.reviewed = false,
    this.rawText = '',
    this.imageName,
    List<ReceiptItem>? items,
  }) : items = items ?? [];

  List<String> get issues {
    final result = <String>[];
    if (merchant.trim().isEmpty) result.add('Add the store name.');
    if (date == null) result.add('Confirm the purchase date.');
    if (currency.isEmpty) {
      result.add('Choose the currency; a dollar sign alone is ambiguous.');
    }
    if (total == null) result.add('Confirm the final total.');
    if (items.isEmpty) {
      result.add('No items detected. You can add them manually.');
    }
    if (items.any((i) => i.amount == null)) {
      result.add('Some item prices need checking.');
    }
    if (subtotal != null &&
        items.isNotEmpty &&
        items.every((i) => i.amount != null)) {
      final sum = items.fold<int>(0, (a, b) => a + b.amount!);
      if ((sum - subtotal!).abs() > 1) {
        result.add(
          'Item amounts do not match the subtotal. Check discounts and missing lines.',
        );
      }
    }
    if (subtotal != null && total != null && tax != null) {
      final expected =
          subtotal! + tax! + (tip ?? 0) + (fees ?? 0) - (discount ?? 0);
      if ((expected - total!).abs() > 1) {
        result.add('Subtotal, tax and adjustments do not match the total.');
      }
    }
    return result;
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'createdAt': createdAt,
    'merchant': merchant,
    'date': date,
    'currency': currency,
    'subtotal': subtotal,
    'tax': tax,
    'total': total,
    'tip': tip,
    'fees': fees,
    'discount': discount,
    'category': category,
    'reviewed': reviewed,
    'rawText': rawText,
    'imageName': imageName,
    'items': items.map((i) => i.toJson()).toList(),
  };
  factory Receipt.fromJson(Map<String, dynamic> j) => Receipt(
    id: j['id'] as String,
    createdAt: j['createdAt'] as String,
    merchant: j['merchant'] as String? ?? '',
    date: j['date'] as String?,
    currency: j['currency'] as String? ?? '',
    subtotal: j['subtotal'] as int?,
    tax: j['tax'] as int?,
    total: j['total'] as int?,
    tip: j['tip'] as int?,
    fees: j['fees'] as int?,
    discount: j['discount'] as int?,
    category: j['category'] as String? ?? 'Other',
    reviewed: j['reviewed'] as bool? ?? false,
    rawText: j['rawText'] as String? ?? '',
    imageName: j['imageName'] as String?,
    items: (j['items'] as List? ?? [])
        .map((i) => ReceiptItem.fromJson(Map<String, dynamic>.from(i as Map)))
        .toList(),
  );
  Receipt copy() => Receipt.fromJson(
    jsonDecode(jsonEncode(toJson())) as Map<String, dynamic>,
  );
}

class OcrLine {
  final String text;
  final double left, top, right, bottom;
  OcrLine(this.text, this.left, this.top, this.right, this.bottom);
  factory OcrLine.fromJson(Map<dynamic, dynamic> j) => OcrLine(
    j['text'] as String,
    (j['left'] as num).toDouble(),
    (j['top'] as num).toDouble(),
    (j['right'] as num).toDouble(),
    (j['bottom'] as num).toDouble(),
  );
}

class ReceiptParser {
  static final _price = RegExp(
    r'(-?[\$€£]?\s*\d[\d,]*\.\d{2})\s*(?:[A-Z*]{1,2})?$',
    caseSensitive: false,
  );
  static final _metadata = RegExp(
    r'\b(sub\s*total|total|tax|vat|gst|cash|change|tender|visa|mastercard|debit|credit|balance|payment|discount|coupon|savings|tip|gratuity|fee|auth|approval|transaction|terminal|cashier|receipt|tel|phone|thank|welcome|items? sold)\b',
    caseSensitive: false,
  );

  // OCR may return all descriptions in one block and all prices in another.
  // Reassemble spatial rows before interpreting any values.
  static List<String> rows(List<OcrLine> source) {
    final lines = [...source]..sort((a, b) => a.top.compareTo(b.top));
    final groups = <List<OcrLine>>[];
    for (final line in lines) {
      List<OcrLine>? match;
      for (final row in groups.reversed.take(4)) {
        final anchor = row.first;
        final height = (anchor.bottom - anchor.top).abs();
        final delta =
            ((line.top + line.bottom) / 2 - (anchor.top + anchor.bottom) / 2)
                .abs();
        if (delta <= height * 0.45 &&
            row.every((x) => line.left >= x.right || line.right <= x.left)) {
          match = row;
          break;
        }
      }
      if (match == null) {
        groups.add([line]);
      } else {
        match.add(line);
      }
    }
    return groups.map((row) {
      row.sort((a, b) => a.left.compareTo(b.left));
      return row.map((l) => l.text).join(' ');
    }).toList();
  }

  static Receipt parse({
    required String text,
    List<OcrLine> lines = const [],
    String? imageName,
    DateTime? now,
  }) {
    final time = now ?? DateTime.now();
    final receipt = Receipt(
      id: time.microsecondsSinceEpoch.toString(),
      createdAt: time.toIso8601String(),
      rawText: text,
      imageName: imageName,
    );
    final input = lines.isEmpty ? text.split('\n') : rows(lines);
    var sawSummary = false;
    final totals = <int>{};
    final currenciesFound = <String>{};
    for (var index = 0; index < input.length; index++) {
      final line = input[index].trim();
      if (line.isEmpty) continue;
      receipt.date ??= _date(line);
      for (final match in RegExp(
        r'\b(USD|CAD|AUD|EUR|GBP)\b',
      ).allMatches(line.toUpperCase())) {
        currenciesFound.add(match[1]!);
      }
      if (line.contains('€')) currenciesFound.add('EUR');
      if (line.contains('£')) currenciesFound.add('GBP');
      if (index < 5 &&
          receipt.merchant.isEmpty &&
          RegExp(r'[A-Za-z]{3}').hasMatch(line) &&
          !_metadata.hasMatch(line) &&
          !_price.hasMatch(line) &&
          !RegExp(r'^\d').hasMatch(line)) {
        receipt.merchant = line;
      }
      final priceMatch = _price.firstMatch(line);
      final amount = priceMatch == null ? null : parseMoney(priceMatch[1]!);
      if (amount == null) continue;
      final label = line.substring(0, priceMatch!.start).trim();
      if (RegExp(
        r'^(sub\s*total|net total)\b',
        caseSensitive: false,
      ).hasMatch(label)) {
        receipt.subtotal = amount;
        sawSummary = true;
        continue;
      }
      if (RegExp(
        r'^(grand\s+total|total(?:\s+due)?|amount\s+due|balance\s+due)\s*[:\-]?$',
        caseSensitive: false,
      ).hasMatch(label)) {
        totals.add(amount);
        sawSummary = true;
        continue;
      }
      if (RegExp(
        r'^(sales\s+)?(tax|vat|gst)\b',
        caseSensitive: false,
      ).hasMatch(label)) {
        receipt.tax = (receipt.tax ?? 0) + amount;
        sawSummary = true;
        continue;
      }
      if (RegExp(r'^(tip|gratuity)\b', caseSensitive: false).hasMatch(label)) {
        receipt.tip = amount;
        continue;
      }
      if (RegExp(
        r'^(service\s+fee|delivery\s+fee|fees?)\b',
        caseSensitive: false,
      ).hasMatch(label)) {
        receipt.fees = (receipt.fees ?? 0) + amount;
        continue;
      }
      if (RegExp(
        r'^(discount|coupon)\b',
        caseSensitive: false,
      ).hasMatch(label)) {
        if (sawSummary) {
          receipt.discount = (receipt.discount ?? 0) + amount.abs();
        } else {
          receipt.items.add(
            ReceiptItem(
              description: label,
              rawDescription: line,
              amount: -amount.abs(),
            ),
          );
        }
        continue;
      }
      if (_metadata.hasMatch(label) ||
          sawSummary ||
          label.isEmpty ||
          !RegExp(r'[A-Za-z]').hasMatch(label)) {
        continue;
      }
      final quantity = RegExp(r'^(\d+(?:\.\d+)?)\s*[xX@]\s*').firstMatch(label);
      receipt.items.add(
        ReceiptItem(
          description: label,
          rawDescription: line,
          amount: amount,
          quantity: quantity == null ? null : double.tryParse(quantity[1]!),
        ),
      );
    }
    // Conflicting totals are not resolved by guessing the largest number.
    receipt.total = totals.length == 1 ? totals.single : null;
    receipt.currency = currenciesFound.length == 1
        ? currenciesFound.single
        : '';
    return receipt;
  }

  static String? _date(String text) {
    final iso = RegExp(
      r'\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b',
    ).firstMatch(text);
    final us = RegExp(r'\b(\d{1,2})/(\d{1,2})/(20\d{2})\b').firstMatch(text);
    if (iso == null && us == null) return null;
    final year = int.parse(iso?[1] ?? us![3]!);
    final month = int.parse(iso?[2] ?? us![1]!);
    final day = int.parse(iso?[3] ?? us![2]!);
    final value = DateTime(year, month, day);
    if (value.year != year || value.month != month || value.day != day) {
      return null;
    }
    return '${year.toString().padLeft(4, '0')}-${month.toString().padLeft(2, '0')}-${day.toString().padLeft(2, '0')}';
  }
}
