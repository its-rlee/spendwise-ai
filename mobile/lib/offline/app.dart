import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'local_store.dart';
import 'receipt.dart';

const _ink = Color(0xFF18251F);
const _lime = Color(0xFFD5F76A);
const _paper = Color(0xFFF7F7EF);
const currencies = ['USD', 'CAD', 'AUD', 'EUR', 'GBP'];
const categories = [
  'Groceries',
  'Dining',
  'Shopping',
  'Transport',
  'Health',
  'Home',
  'Other',
];

class OfflineSpendWiseApp extends StatelessWidget {
  const OfflineSpendWiseApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'SpendWise',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      fontFamily: 'Roboto',
      useMaterial3: true,
      scaffoldBackgroundColor: _paper,
      colorScheme: ColorScheme.fromSeed(
        seedColor: _ink,
        primary: _ink,
        secondary: _lime,
        surface: _paper,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: _paper,
        foregroundColor: _ink,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 54),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(18),
          ),
        ),
      ),
      textTheme: const TextTheme(
        headlineLarge: TextStyle(
          fontSize: 38,
          fontWeight: FontWeight.w800,
          letterSpacing: -1.5,
          color: _ink,
        ),
        headlineMedium: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          letterSpacing: -0.8,
          color: _ink,
        ),
      ),
    ),
    home: const ReceiptHome(),
  );
}

class ReceiptHome extends StatefulWidget {
  const ReceiptHome({super.key});
  @override
  State<ReceiptHome> createState() => _ReceiptHomeState();
}

class _ReceiptHomeState extends State<ReceiptHome> {
  final store = LocalStore();
  List<Receipt> receipts = [];
  bool loading = true, busy = false;
  String? error;
  String query = '', currency = 'USD';
  int tab = 0;
  bool get supported =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
  @override
  void initState() {
    super.initState();
    _load();
  }

  void message(String text) {
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
    }
  }

  String failure(Object e) => e is PlatformException
      ? e.message ?? 'Please try again.'
      : 'Could not load or save receipts. Your existing data has not been replaced.';

  Future<void> _load() async {
    if (!supported) {
      setState(() {
        loading = false;
        error =
            'Install the Android app to scan and save receipts on your device.';
      });
      return;
    }
    try {
      final loaded = await store.load();
      if (mounted) {
        setState(() {
          receipts = loaded;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = failure(e));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _scan({bool import = false}) async {
    setState(() => busy = true);
    try {
      final receipt = await store.scan(import: import);
      if (receipt == null) return;
      final updated = [receipt, ...receipts];
      await store.save(
        updated,
      ); // Persist the draft before navigating or reviewing.
      if (!mounted) return;
      setState(() => receipts = updated);
      await _edit(receipt);
    } catch (e) {
      message(failure(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _edit(Receipt receipt) async {
    final result = await Navigator.of(context).push<Receipt>(
      MaterialPageRoute(
        builder: (_) => ReceiptEditor(
          receipt: receipt.copy(),
          imageDirectory: store.imageDirectory,
          onSave: (edited) async {
            final updated = receipts
                .map((r) => r.id == edited.id ? edited : r)
                .toList();
            await store.save(updated);
            if (mounted) setState(() => receipts = updated);
          },
        ),
      ),
    );
    if (result != null) {
      message(
        result.reviewed
            ? 'Receipt saved. You’re all set.'
            : 'Draft saved for later.',
      );
    }
  }

  Future<void> _delete(Receipt receipt) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this receipt?'),
        content: const Text(
          'Its saved details and photo will be removed from this device.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    setState(() => busy = true);
    try {
      final updated = receipts.where((r) => r.id != receipt.id).toList();
      await store.save(updated);
      if (mounted) setState(() => receipts = updated);
      if (receipt.imageName != null) {
        await store.deleteImage(receipt.imageName!);
      }
    } catch (e) {
      message(failure(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _export() async {
    setState(() => busy = true);
    try {
      if (await store.export(receipts)) {
        message('Receipt details exported. Photos are kept in the app.');
      }
    } catch (e) {
      message(failure(e));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  void _about() => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) => SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(24, 8, 24, 32),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'Your receipts.\nYour device.',
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            const SizedBox(height: 16),
            const Text(
              'No account, subscription or cloud AI calls. Recognition and receipt parsing run on your phone. '
              'The camera scanner may need a one-time Google Play services download. Import photo works with the bundled text recognizer.',
            ),
            const SizedBox(height: 16),
            const Text(
              'Always check the result. This version reads Latin-script receipts, uses US month/day/year for slash dates, '
              'and supports USD, CAD, AUD, EUR and GBP. It does not guess missing prices or expand product abbreviations.',
            ),
            const SizedBox(height: 16),
            const Text(
              'Receipts stay in private app storage. Uninstalling or clearing app data deletes them. '
              'Export saves a readable JSON copy of details and recognized text, without photos. Keep that file private.',
            ),
            const SizedBox(height: 16),
            const Text(
              'Built with Google ML Kit. No cloud LLM is used in this version.',
            ),
          ],
        ),
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    final now = DateTime.now();
    final month = '${now.year}-${now.month.toString().padLeft(2, '0')}';
    final monthly = receipts
        .where(
          (r) =>
              r.reviewed &&
              r.currency == currency &&
              (r.date ?? '').startsWith(month),
        )
        .toList();
    final total = monthly.fold<int>(0, (sum, r) => sum + (r.total ?? 0));
    final drafts = receipts.where((r) => !r.reviewed).length;
    final visible = receipts
        .where(
          (r) =>
              '${r.merchant} ${r.category} ${r.items.map((i) => i.description).join(' ')}'
                  .toLowerCase()
                  .contains(query.toLowerCase()),
        )
        .toList();
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          'spendwise',
          style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: -1),
        ),
        actions: [
          IconButton(
            tooltip: 'Export receipt details',
            onPressed: busy || loading || error != null ? null : _export,
            icon: const Icon(Icons.ios_share),
          ),
          IconButton(
            tooltip: 'Privacy and help',
            onPressed: _about,
            icon: const Icon(Icons.shield_outlined),
          ),
        ],
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (i) => setState(() => tab = i),
        indicatorColor: _lime,
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.space_dashboard_outlined),
            label: 'Today',
          ),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            label: 'Receipts',
          ),
          NavigationDestination(
            icon: Icon(Icons.bar_chart_rounded),
            label: 'Insights',
          ),
        ],
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: loading
                ? const Center(child: CircularProgressIndicator())
                : ListView(
                    padding: const EdgeInsets.fromLTRB(22, 12, 22, 28),
                    children: [
                      if (error != null) ...[
                        Text(error!),
                        const SizedBox(height: 12),
                        if (supported)
                          OutlinedButton(
                            onPressed: _load,
                            child: const Text('Retry loading'),
                          ),
                      ] else ...[
                        if (tab == 0) ...[
                          Text(
                            'Small receipts.\nBigger clarity.',
                            style: Theme.of(context).textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'Capture a purchase. Keep your day moving.',
                          ),
                          const SizedBox(height: 24),
                          Container(
                            padding: const EdgeInsets.all(24),
                            decoration: BoxDecoration(
                              color: _ink,
                              borderRadius: BorderRadius.circular(28),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text(
                                  'THIS MONTH · REVIEWED RECEIPTS',
                                  style: TextStyle(
                                    color: _lime,
                                    fontSize: 11,
                                    fontWeight: FontWeight.w700,
                                    letterSpacing: 1.2,
                                  ),
                                ),
                                const SizedBox(height: 12),
                                Text(
                                  '$currency ${money(total)}',
                                  style: const TextStyle(
                                    color: Colors.white,
                                    fontSize: 36,
                                    fontWeight: FontWeight.w800,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                Text(
                                  '${monthly.length} purchases saved • $drafts to review',
                                  style: const TextStyle(color: Colors.white70),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 20),
                          FilledButton.icon(
                            style: FilledButton.styleFrom(
                              backgroundColor: _lime,
                              foregroundColor: _ink,
                            ),
                            onPressed: busy ? null : () => _scan(),
                            icon: const Icon(Icons.document_scanner_outlined),
                            label: Text(
                              busy ? 'Reading your receipt…' : 'Scan a receipt',
                            ),
                          ),
                          const SizedBox(height: 8),
                          OutlinedButton.icon(
                            onPressed: busy ? null : () => _scan(import: true),
                            icon: const Icon(Icons.photo_library_outlined),
                            label: const Text('Import photo'),
                          ),
                          if (busy)
                            const Padding(
                              padding: EdgeInsets.all(12),
                              child: LinearProgressIndicator(),
                            ),
                          const Padding(
                            padding: EdgeInsets.symmetric(vertical: 14),
                            child: Text(
                              'ON-DEVICE • NO ACCOUNT • NO SCAN FEES',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 10,
                                letterSpacing: 1.2,
                              ),
                            ),
                          ),
                        ],
                        if (tab == 2) ...[
                          Text(
                            'See where it goes.',
                            style: Theme.of(context).textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 12),
                          const Text(
                            'This month, from receipts you have reviewed. Currencies are never combined.',
                          ),
                          const SizedBox(height: 18),
                          _currencyPicker(),
                          const SizedBox(height: 12),
                          Text(
                            '$currency ${money(total)}',
                            style: Theme.of(context).textTheme.headlineLarge,
                          ),
                          const SizedBox(height: 24),
                          for (final category in categories) ...[
                            Builder(
                              builder: (context) {
                                final amount = monthly
                                    .where((r) => r.category == category)
                                    .fold<int>(0, (s, r) => s + (r.total ?? 0));
                                return Padding(
                                  padding: const EdgeInsets.only(bottom: 20),
                                  child: Column(
                                    children: [
                                      Row(
                                        children: [
                                          Expanded(child: Text(category)),
                                          Text(
                                            '$currency ${money(amount)}',
                                            style: const TextStyle(
                                              fontWeight: FontWeight.w700,
                                            ),
                                          ),
                                        ],
                                      ),
                                      const SizedBox(height: 8),
                                      LinearProgressIndicator(
                                        value: total <= 0
                                            ? 0
                                            : (amount / total).clamp(0.0, 1.0),
                                        minHeight: 8,
                                        borderRadius: BorderRadius.circular(8),
                                        color: _ink,
                                        backgroundColor: _lime.withValues(
                                          alpha: 0.45,
                                        ),
                                      ),
                                    ],
                                  ),
                                );
                              },
                            ),
                          ],
                          if (monthly.isEmpty)
                            const Text(
                              'Your first reviewed receipt starts the picture.',
                            ),
                        ] else ...[
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  tab == 0
                                      ? 'Recent receipts'
                                      : 'Your receipt drawer',
                                  style: Theme.of(
                                    context,
                                  ).textTheme.headlineMedium,
                                ),
                              ),
                              if (tab == 0)
                                SizedBox(width: 85, child: _currencyPicker()),
                            ],
                          ),
                          const SizedBox(height: 14),
                          if (tab == 1)
                            TextField(
                              onChanged: (v) => setState(() => query = v),
                              decoration: const InputDecoration(
                                prefixIcon: Icon(Icons.search),
                                hintText: 'Search stores or items',
                              ),
                            ),
                          if (visible.isEmpty)
                            Container(
                              margin: const EdgeInsets.only(top: 16),
                              padding: const EdgeInsets.all(28),
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(24),
                              ),
                              child: Text(
                                query.isEmpty
                                    ? 'A fresh start. Scan your first receipt to see it here.'
                                    : 'No matching receipts.',
                              ),
                            ),
                          for (final receipt
                              in (tab == 0 ? receipts.take(5) : visible))
                            Padding(
                              padding: const EdgeInsets.only(top: 10),
                              child: Material(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(20),
                                child: ListTile(
                                  contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 16,
                                    vertical: 8,
                                  ),
                                  leading: CircleAvatar(
                                    backgroundColor: receipt.reviewed
                                        ? _lime
                                        : const Color(0xFFFFE6AD),
                                    child: Icon(
                                      receipt.reviewed
                                          ? Icons.receipt_long
                                          : Icons.edit_outlined,
                                      color: _ink,
                                    ),
                                  ),
                                  title: Text(
                                    receipt.merchant.isEmpty
                                        ? 'New receipt'
                                        : receipt.merchant,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  subtitle: Text(
                                    receipt.reviewed
                                        ? '${receipt.date ?? 'No date'} · ${receipt.category}'
                                        : 'Draft · tap to review',
                                  ),
                                  trailing: Row(
                                    mainAxisSize: MainAxisSize.min,
                                    children: [
                                      Text(
                                        receipt.total == null
                                            ? '—'
                                            : '${receipt.currency} ${money(receipt.total)}',
                                      ),
                                      PopupMenuButton<String>(
                                        enabled: !busy,
                                        onSelected: (_) => _delete(receipt),
                                        itemBuilder: (_) => [
                                          const PopupMenuItem(
                                            value: 'delete',
                                            child: Text('Delete'),
                                          ),
                                        ],
                                      ),
                                    ],
                                  ),
                                  onTap: busy ? null : () => _edit(receipt),
                                ),
                              ),
                            ),
                        ],
                      ],
                    ],
                  ),
          ),
        ),
      ),
    );
  }

  Widget _currencyPicker() => DropdownButtonFormField<String>(
    isExpanded: true,
    initialValue: currency,
    decoration: const InputDecoration(
      contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
    ),
    items: currencies
        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
        .toList(),
    onChanged: (c) => setState(() => currency = c!),
  );
}

class ReceiptEditor extends StatefulWidget {
  final Receipt receipt;
  final String imageDirectory;
  final Future<void> Function(Receipt) onSave;
  const ReceiptEditor({
    super.key,
    required this.receipt,
    required this.imageDirectory,
    required this.onSave,
  });
  @override
  State<ReceiptEditor> createState() => _ReceiptEditorState();
}

class _ReceiptEditorState extends State<ReceiptEditor> {
  final form = GlobalKey<FormState>();
  bool saving = false;
  Receipt get receipt => widget.receipt;
  Future<void> save(bool reviewed) async {
    if (!form.currentState!.validate()) return;
    if (reviewed &&
        (receipt.merchant.trim().isEmpty ||
            receipt.total == null ||
            receipt.currency.isEmpty ||
            receipt.date == null)) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Confirm the store, date, currency and total first. Or save as a draft.',
          ),
        ),
      );
      return;
    }
    if (reviewed && receipt.issues.isNotEmpty) {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Keep these details?'),
          content: Text(
            '${receipt.issues.join('\n\n')}\n\nSave only if you have checked the receipt.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Check again'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('I checked it'),
            ),
          ],
        ),
      );
      if (confirmed != true) return;
    }
    setState(() => saving = true);
    receipt.reviewed = reviewed;
    try {
      await widget.onSave(receipt);
      if (mounted) Navigator.pop(context, receipt);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not save. Free up device storage and try again.',
            ),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  Widget amountField(
    String label,
    int? value,
    void Function(int?) change, {
    bool signed = false,
  }) => TextFormField(
    initialValue: money(value),
    decoration: InputDecoration(labelText: label),
    keyboardType: TextInputType.numberWithOptions(
      decimal: true,
      signed: signed,
    ),
    validator: (text) => text == null || text.trim().isEmpty
        ? null
        : parseMoney(text) == null || (!signed && parseMoney(text)! < 0)
        ? 'Enter a valid ${signed ? '' : 'positive '}amount'
        : null,
    onChanged: (text) => setState(() => change(parseMoney(text))),
  );

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !saving,
    child: Scaffold(
      appBar: AppBar(title: const Text('Check your receipt')),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 720),
            child: Form(
              key: form,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(22, 8, 22, 32),
                children: [
                  Text(
                    'A quick check.\nThen you’re done.',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Recognition can miss details. Compare the photo, especially prices, quantities and discounts.',
                  ),
                  const SizedBox(height: 16),
                  if (receipt.imageName != null &&
                      widget.imageDirectory.isNotEmpty)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(20),
                      child: SizedBox(
                        height: 230,
                        child: InteractiveViewer(
                          minScale: 1,
                          maxScale: 6,
                          child: Image.file(
                            File(
                              '${widget.imageDirectory}/${receipt.imageName}',
                            ),
                            fit: BoxFit.contain,
                            errorBuilder: (_, error, stack) => const Center(
                              child: Text('Receipt photo unavailable'),
                            ),
                          ),
                        ),
                      ),
                    ),
                  const SizedBox(height: 18),
                  if (receipt.issues.isNotEmpty)
                    Container(
                      padding: const EdgeInsets.all(16),
                      margin: const EdgeInsets.only(bottom: 18),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFFEBC4),
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: Text(
                        receipt.issues.join('\n'),
                        style: const TextStyle(color: Color(0xFF644300)),
                      ),
                    ),
                  TextFormField(
                    initialValue: receipt.merchant,
                    decoration: const InputDecoration(labelText: 'Store'),
                    onChanged: (v) =>
                        setState(() => receipt.merchant = v.trim()),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: () async {
                      final date = await showDatePicker(
                        context: context,
                        initialDate:
                            DateTime.tryParse(receipt.date ?? '') ??
                            DateTime.now(),
                        firstDate: DateTime(1900),
                        lastDate: DateTime(2100),
                      );
                      if (date != null && mounted) {
                        setState(
                          () => receipt.date = date.toIso8601String().substring(
                            0,
                            10,
                          ),
                        );
                      }
                    },
                    icon: const Icon(Icons.calendar_today_outlined),
                    label: Text(receipt.date ?? 'Choose purchase date'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: receipt.currency.isEmpty
                        ? null
                        : receipt.currency,
                    decoration: const InputDecoration(labelText: 'Currency'),
                    items: currencies
                        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                        .toList(),
                    onChanged: (v) => setState(() => receipt.currency = v!),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    initialValue: receipt.category,
                    decoration: const InputDecoration(labelText: 'Category'),
                    items: categories
                        .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                        .toList(),
                    onChanged: (v) => setState(() => receipt.category = v!),
                  ),
                  const SizedBox(height: 12),
                  amountField(
                    'Final total',
                    receipt.total,
                    (v) => receipt.total = v,
                  ),
                  const SizedBox(height: 12),
                  ExpansionTile(
                    title: const Text('Subtotal, tax & adjustments'),
                    tilePadding: EdgeInsets.zero,
                    children: [
                      amountField(
                        'Subtotal',
                        receipt.subtotal,
                        (v) => receipt.subtotal = v,
                      ),
                      const SizedBox(height: 12),
                      amountField(
                        'Tax amount (not percent)',
                        receipt.tax,
                        (v) => receipt.tax = v,
                      ),
                      const SizedBox(height: 12),
                      amountField('Tip', receipt.tip, (v) => receipt.tip = v),
                      const SizedBox(height: 12),
                      amountField(
                        'Fees',
                        receipt.fees,
                        (v) => receipt.fees = v,
                      ),
                      const SizedBox(height: 12),
                      amountField(
                        'Discount after subtotal',
                        receipt.discount,
                        (v) => receipt.discount = v,
                      ),
                      const SizedBox(height: 12),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'Purchased items',
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  for (final item in receipt.items)
                    Container(
                      key: ObjectKey(item),
                      padding: const EdgeInsets.all(14),
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(18),
                      ),
                      child: Column(
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: TextFormField(
                                  initialValue: item.description,
                                  decoration: const InputDecoration(
                                    labelText: 'Item',
                                  ),
                                  validator: (v) =>
                                      v == null || v.trim().isEmpty
                                      ? 'Add an item name'
                                      : null,
                                  onChanged: (v) => item.description = v,
                                ),
                              ),
                              IconButton(
                                tooltip: 'Remove item',
                                onPressed: () =>
                                    setState(() => receipt.items.remove(item)),
                                icon: const Icon(Icons.close),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          amountField(
                            'Line amount (negative for discounts)',
                            item.amount,
                            (v) => item.amount = v,
                            signed: true,
                          ),
                          ExpansionTile(
                            title: const Text('Quantity & source'),
                            tilePadding: EdgeInsets.zero,
                            children: [
                              TextFormField(
                                initialValue: item.quantity?.toString() ?? '',
                                decoration: const InputDecoration(
                                  labelText: 'Printed quantity',
                                ),
                                keyboardType:
                                    const TextInputType.numberWithOptions(
                                      decimal: true,
                                    ),
                                validator: (v) => v == null || v.isEmpty
                                    ? null
                                    : double.tryParse(v) == null ||
                                          !double.parse(v).isFinite ||
                                          double.parse(v) <= 0
                                    ? 'Enter a positive quantity'
                                    : null,
                                onChanged: (v) =>
                                    item.quantity = double.tryParse(v),
                              ),
                              const SizedBox(height: 8),
                              amountField(
                                'Printed unit price',
                                item.unitPrice,
                                (v) => item.unitPrice = v,
                              ),
                              if (item.rawDescription.isNotEmpty)
                                Padding(
                                  padding: const EdgeInsets.all(8),
                                  child: Text(
                                    'Recognized: ${item.rawDescription}',
                                  ),
                                ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  OutlinedButton.icon(
                    onPressed: () => setState(
                      () => receipt.items.add(ReceiptItem(description: '')),
                    ),
                    icon: const Icon(Icons.add),
                    label: const Text('Add an item'),
                  ),
                  ExpansionTile(
                    tilePadding: EdgeInsets.zero,
                    title: const Text('Original recognized text'),
                    children: [
                      Align(
                        alignment: Alignment.centerLeft,
                        child: SelectableText(
                          receipt.rawText.isEmpty
                              ? 'No text found. You can enter the details manually.'
                              : receipt.rawText,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  FilledButton.icon(
                    onPressed: saving ? null : () => save(true),
                    icon: const Icon(Icons.check),
                    label: Text(saving ? 'Saving…' : 'Save receipt'),
                  ),
                  TextButton(
                    onPressed: saving ? null : () => save(false),
                    child: const Text('Save draft for later'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
