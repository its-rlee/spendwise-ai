import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/offline/app.dart';
import 'package:mobile/offline/local_store.dart';
import 'package:mobile/offline/receipt.dart';

void main() {
  test(
    'preserves cents exactly and rejects malformed or excessive precision',
    () {
      expect(parseMoney('1,234.56'), 123456);
      expect(parseMoney('-0.10'), -10);
      expect(parseMoney('8.00%'), isNull);
      expect(parseMoney('1.999'), isNull);
      expect(parseMoney('2,50'), isNull);
      expect(parseMoney('1,2.00'), isNull);
      expect(money(-101), '-1.01');
    },
  );

  test(
    'recognizes totals without treating tender or tax rate as a purchase',
    () {
      final result = ReceiptParser.parse(
        text: '''CORNER MARKET
10/21/2026
MILK 4.25
BREAD 2.75
SUBTOTAL 7.00
TAX 8.00%
TOTAL 7.56
VISA 7.56
CASH 20.00
CHANGE 12.44''',
      );
      expect(result.items.map((i) => i.amount), [425, 275]);
      expect(result.subtotal, 700);
      expect(result.tax, isNull);
      expect(result.total, 756);
      expect(result.date, '2026-10-21');
      expect(result.currency, '');
      expect(result.reviewed, isFalse);
    },
  );

  test(
    'reassembles independently recognized price and description columns',
    () {
      final result = ReceiptParser.parse(
        text: 'disordered OCR',
        lines: [
          OcrLine('MILK', 0, 30, 70, 50),
          OcrLine('BREAD', 0, 60, 80, 80),
          OcrLine('4.25', 180, 31, 220, 51),
          OcrLine('2.75', 180, 60, 220, 80),
          OcrLine('TOTAL', 0, 90, 80, 110),
          OcrLine('7.00', 180, 91, 220, 111),
        ],
      );
      expect(result.items.map((i) => i.amount), [425, 275]);
      expect(result.total, 700);
    },
  );

  test('conflicting totals and impossible dates stay unknown', () {
    final result = ReceiptParser.parse(
      text: 'SHOP\n02/31/2026\nTOTAL 10.00\nTOTAL 12.00',
    );
    expect(result.total, isNull);
    expect(result.date, isNull);
  });

  test('preserves discounts and detects incomplete item extraction', () {
    final result = ReceiptParser.parse(
      text:
          'SHOP USD\nSOAP 5.00\nCOUPON 1.00\nSUBTOTAL 6.00\nTAX 0.50\nTOTAL 6.50',
    );
    expect(result.items.last.amount, -100);
    expect(result.issues.any((i) => i.contains('Item amounts')), isTrue);
    expect(result.currency, 'USD');
  });

  test('round trips reviewed records without losing provenance or money', () {
    final result = ReceiptParser.parse(
      text: 'SHOP\nMILK 4.25\nTOTAL 4.25',
      imageName: 'abc.jpg',
    );
    result.reviewed = true;
    final copy = Receipt.fromJson(
      jsonDecode(jsonEncode(result.toJson())) as Map<String, dynamic>,
    );
    expect(copy.total, 425);
    expect(copy.items.first.rawDescription, 'MILK 4.25');
    expect(copy.reviewed, isTrue);
    expect(copy.imageName, 'abc.jpg');
  });

  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(LocalStore.channel, (call) async {
          if (call.method == 'imagePath') return '/private/receipts';
          return null;
        });
  });
  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(LocalStore.channel, null);
  });
  test('storage load failure never overwrites unreadable receipts', () async {
    var writes = 0;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(LocalStore.channel, (call) async {
          if (call.method == 'imagePath') return '/private/receipts';
          if (call.method == 'load') return '{broken';
          if (call.method == 'save') writes++;
          return null;
        });
    await expectLater(LocalStore().load(), throwsFormatException);
    expect(writes, 0);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(LocalStore.channel, null);
  });

  testWidgets('launches without a Supabase configuration or login', (
    tester,
  ) async {
    await tester.pumpWidget(const OfflineSpendWiseApp());
    await tester.pumpAndSettle();
    expect(find.text('spendwise'), findsOneWidget);
    expect(find.text('Today'), findsOneWidget);
    expect(find.text('Receipts'), findsOneWidget);
    expect(find.text('Insights'), findsOneWidget);
    expect(find.byType(NavigationBar), findsOneWidget);
  });

  testWidgets('review requires merchant, date, currency and total', (
    tester,
  ) async {
    var saved = false;
    await tester.pumpWidget(
      MaterialApp(
        home: ReceiptEditor(
          receipt: Receipt(id: '1', createdAt: '2026-10-21'),
          imageDirectory: '',
          onSave: (_) async {
            saved = true;
          },
        ),
      ),
    );
    await tester.scrollUntilVisible(
      find.text('Save receipt'),
      350,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('Save receipt'));
    await tester.pumpAndSettle();
    expect(saved, isFalse);
    expect(find.textContaining('Confirm the store'), findsOneWidget);
  });
}
