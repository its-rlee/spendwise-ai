import 'dart:convert';

import 'package:flutter/services.dart';

import 'receipt.dart';

class LocalStore {
  static const channel = MethodChannel('spendwise/local');
  String imageDirectory = '';
  Future<List<Receipt>> load() async {
    imageDirectory = await channel.invokeMethod<String>('imagePath') ?? '';
    final value = await channel.invokeMethod<String>('load');
    if (value == null) return [];
    final data = jsonDecode(value) as Map<String, dynamic>;
    if (data['version'] != 1) {
      throw const FormatException('Unsupported receipt version');
    }
    return (data['receipts'] as List)
        .map((e) => Receipt.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  String encode(List<Receipt> receipts) => jsonEncode({
    'version': 1,
    'receipts': receipts.map((r) => r.toJson()).toList(),
  });
  Future<void> save(List<Receipt> receipts) =>
      channel.invokeMethod<void>('save', {'json': encode(receipts)});
  Future<bool> export(List<Receipt> receipts) async =>
      await channel.invokeMethod<bool>('export', {'json': encode(receipts)}) ??
      false;
  Future<Receipt?> scan({bool import = false}) async {
    final data = await channel.invokeMapMethod<dynamic, dynamic>(
      import ? 'import' : 'scan',
    );
    if (data == null) return null;
    return ReceiptParser.parse(
      text: data['text'] as String,
      imageName: data['imageName'] as String?,
      lines: (data['lines'] as List)
          .map((l) => OcrLine.fromJson(l as Map))
          .toList(),
    );
  }

  Future<void> deleteImage(String name) =>
      channel.invokeMethod<void>('deleteImage', {'name': name});
}
