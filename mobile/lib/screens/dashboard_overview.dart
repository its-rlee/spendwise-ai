import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../services/dashboard_models.dart';
import '../services/spendwise_api.dart';
import '../theme/terminal_theme.dart';

/// Dashboard summaries are deterministic database reads, not AI estimates.
/// Parent owns scanning/navigation; this widget owns only its filters and data.
class DashboardOverview extends StatefulWidget {
  const DashboardOverview({
    super.key,
    required this.onScan,
    required this.onResume,
  });

  final VoidCallback onScan;
  final ValueChanged<PendingReceipt> onResume;

  @override
  State<DashboardOverview> createState() => _DashboardOverviewState();
}

class _DashboardOverviewState extends State<DashboardOverview> {
  static const _ink = TerminalColors.phosphor;
  static const _lime = TerminalColors.amber;
  static const _muted = TerminalColors.muted;
  static const _soft = TerminalColors.raised;

  final _api = SpendwiseApi();
  SpendingDashboard? _data;
  String? _error;
  String _currency = 'USD';
  DateTime _selected = DateTime.utc(
    DateTime.now().toUtc().year,
    DateTime.now().toUtc().month,
  );
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  String get _monthKey =>
      '${_selected.year}-${_selected.month.toString().padLeft(2, '0')}';

  String _monthTitle(String value) {
    const names = [
      'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
    ];
    final pieces = value.split('-');
    if (pieces.length != 2) return value;
    final index = int.tryParse(pieces[1]) ?? 0;
    if (index < 1 || index > 12) return value;
    return '${names[index - 1]} ${pieces[0]}';
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _api.getDashboard(
        currency: _currency,
        month: _monthKey,
      );
      if (mounted) setState(() => _data = response);
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = error is ApiException
              ? error.message
              : 'Could not load your spending data.';
        });
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _chooseMonth() async {
    final now = DateTime.now().toUtc();
    final picked = await showDatePicker(
      context: context,
      initialDate: _selected,
      firstDate: DateTime.utc(2000),
      lastDate: DateTime.utc(now.year, now.month, now.day),
      initialDatePickerMode: DatePickerMode.year,
      helpText: 'Select a month to review',
    );
    if (!mounted || picked == null) return;
    setState(() {
      _selected = DateTime.utc(picked.year, picked.month);
    });
    await _load();
  }

  String _price(String amount, String currency) {
    final value = double.tryParse(amount);
    if (value == null) return '$currency $amount';
    final formatted = value.toStringAsFixed(2).replaceAllMapped(
      RegExp(r'(\d)(?=(\d{3})+\.)'),
      (match) => '${match[1]},',
    );
    return '$currency $formatted';
  }

  Widget _panel(Widget child, {EdgeInsets padding = const EdgeInsets.all(18)}) {
    return TerminalPanel(padding: padding, child: child);
  }

  Widget _section(String title, Widget child, {String? subtitle}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 25),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TerminalSectionTitle(title),
          if (subtitle != null) ...[
            const SizedBox(height: 7),
            Text(subtitle, style: const TextStyle(
              color: _muted, fontSize: 12,
            )),
          ],
          const SizedBox(height: 12),
          child,
        ],
      ),
    );
  }

  Widget _metric(String title, String value, {bool primary = false}) {
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 130),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(
            color: primary ? _lime : _muted,
            fontSize: 12,
          )),
          const SizedBox(height: 7),
          Text(value, style: TextStyle(
            color: TerminalColors.bright, fontSize: primary ? 28 : 18,
            fontWeight: FontWeight.w800, letterSpacing: -0.8,
          )),
        ],
      ),
    );
  }

  Widget _hero(SpendingDashboard d) {
    final comparison = d.comparisonBasis == 'month_to_date'
        ? 'Previous month, same elapsed days'
        : 'Previous full month';
    return Container(
      padding: const EdgeInsets.all(23),
      margin: const EdgeInsets.only(bottom: 22),
      width: double.infinity,
      decoration: BoxDecoration(
        color: TerminalColors.raised,
        borderRadius: BorderRadius.circular(17),
        border: Border.all(color: TerminalColors.soft),
        boxShadow: [
          BoxShadow(
            color: TerminalColors.phosphor.withValues(alpha: 0.08),
            blurRadius: 26,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.account_balance_wallet_outlined,
                color: _lime, size: 20),
            const SizedBox(width: 9),
            Expanded(child: Text(
              'SPENDING SNAPSHOT  ·  ${_monthTitle(d.month)}',
              style: const TextStyle(
                color: Color(0xFFD0DDD5),
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.2,
              ),
            )),
          ]),
          const SizedBox(height: 22),
          _metric('Spent', _price(d.expenses, d.currency), primary: true),
          const SizedBox(height: 23),
          Wrap(
            spacing: 24,
            runSpacing: 17,
            children: [
              _metric('Received', _price(d.income, d.currency)),
              _metric('Net cash flow', _price(d.net, d.currency)),
            ],
          ),
          const SizedBox(height: 17),
          const Divider(color: Color(0xFF3A5550)),
          const SizedBox(height: 9),
          Text(
            '$comparison: ${_price(d.samePointLastExpenses, d.currency)}',
            style: const TextStyle(color: Color(0xFFC7DCD4), fontSize: 12),
          ),
        ],
      ),
    );
  }

  Widget _chart(SpendingDashboard d) {
    final maximum = d.monthly.fold<double>(
      1, (max, row) => math.max(max, double.tryParse(row.expenses) ?? 0),
    );
    return _panel(Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text('MONTHLY APPROVED EXPENSES',
            style: TextStyle(color: _muted, fontSize: 12, letterSpacing: 1)),
        const SizedBox(height: 18),
        SizedBox(
          height: 165,
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: d.monthly.map((entry) {
              final amount = double.tryParse(entry.expenses) ?? 0;
              final ratio = (amount / maximum).clamp(0.0, 1.0);
              final active = entry.month == d.month;
              return Expanded(child: Tooltip(
                message: '${_monthTitle(entry.month)}: ${_price(entry.expenses, d.currency)}',
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  children: [
                    Text(amount == 0 ? '—' : amount.toStringAsFixed(0),
                        style: const TextStyle(color: _muted, fontSize: 10)),
                    const SizedBox(height: 6),
                    TweenAnimationBuilder<double>(
                      tween: Tween(begin: 4, end: math.max(4, ratio * 113)),
                      duration: MediaQuery.of(context).disableAnimations
                          ? Duration.zero
                          : const Duration(milliseconds: 750),
                      curve: Curves.easeOutCubic,
                      builder: (context, height, _) => Container(
                        height: height,
                        width: 27,
                        decoration: BoxDecoration(
                          color: active ? _ink : TerminalColors.border,
                          borderRadius: const BorderRadius.vertical(
                            top: Radius.circular(4),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(entry.month.substring(5),
                        style: TextStyle(
                          color: active ? _ink : _muted,
                          fontSize: 12,
                          fontWeight: active ? FontWeight.bold : FontWeight.normal,
                        )),
                  ],
                ),
              ));
            }).toList(),
          ),
        ),
        const SizedBox(height: 8),
        const Text('Expense totals include tax; receipts are counted once.',
            style: TextStyle(color: _muted, fontSize: 11)),
      ],
    ));
  }

  Widget _categoryPanel(SpendingDashboard d) {
    if (d.categories.isEmpty) {
      return _panel(const Text(
        'No approved itemized receipts for this month. '
        'Choose an earlier month to review older purchases.',
        style: TextStyle(color: _muted),
      ));
    }
    final maxValue = math.max(
      1, double.tryParse(d.categories.first.amount) ?? 0,
    );
    return _panel(Column(
      children: d.categories.map((row) {
        final value = double.tryParse(row.amount) ?? 0;
        return Padding(
          padding: const EdgeInsets.only(bottom: 17),
          child: Column(children: [
            Row(children: [
              Expanded(child: Text(row.category,
                  style: const TextStyle(fontWeight: FontWeight.w600))),
              const SizedBox(width: 10),
              Text(_price(row.amount, d.currency),
                  style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
            const SizedBox(height: 9),
            ClipRRect(
              borderRadius: BorderRadius.circular(7),
              child: LinearProgressIndicator(
                value: (value / maxValue).clamp(0.0, 1.0),
                minHeight: 8,
                color: TerminalColors.phosphor,
                backgroundColor: _soft,
              ),
            ),
          ]),
        );
      }).toList(),
    ));
  }

  Widget _topProducts(SpendingDashboard d) {
    if (d.topItems.isEmpty) {
      return _panel(const Text('No recorded products this month.',
          style: TextStyle(color: _muted)));
    }
    return _panel(Column(children: d.topItems.map((item) => ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const CircleAvatar(
        backgroundColor: _soft,
        child: Icon(Icons.shopping_bag_outlined, color: _ink),
      ),
      title: Text(item.name, maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontWeight: FontWeight.w600)),
      subtitle: Text(item.category),
      trailing: Text(_price(item.amount, d.currency),
          style: const TextStyle(fontWeight: FontWeight.w700)),
    )).toList()));
  }

  Widget _pending(SpendingDashboard d) {
    return _section(
      'Needs attention',
      _panel(Column(
        children: d.pending.map((receipt) => ListTile(
          contentPadding: EdgeInsets.zero,
          leading: const Icon(Icons.pending_actions_outlined, color: _ink),
          title: Text(receipt.filename, maxLines: 1,
              overflow: TextOverflow.ellipsis),
          subtitle: Text(receipt.status.replaceAll('_', ' ')),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => widget.onResume(receipt),
        )).toList(),
      )),
      subtitle: '${d.pendingCount} saved receipt(s) awaiting processing or approval',
    );
  }

  Widget _purchases(SpendingDashboard d) {
    if (d.purchases.isEmpty) {
      return _panel(Column(
        children: [
          const Icon(Icons.receipt_long_rounded, size: 38, color: _ink),
          const SizedBox(height: 10),
          const Text('NO APPROVED TRANSACTIONS RECORDED.'),
          const SizedBox(height: 10),
          FilledButton.icon(
            onPressed: widget.onScan,
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Scan your first receipt'),
          ),
        ],
      ));
    }
    return _panel(Column(
      children: d.purchases.map((purchase) {
        final expense = purchase.direction == 'debit';
        return ExpansionTile(
          tilePadding: EdgeInsets.zero,
          leading: CircleAvatar(
            backgroundColor: _soft,
            child: Icon(
              expense ? Icons.receipt_long_rounded : Icons.south_west_rounded,
              color: _ink,
            ),
          ),
          title: Text(purchase.merchant,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Text(
            '${purchase.date ?? 'Undated'}  ·  ${purchase.category}',
            maxLines: 2,
          ),
          trailing: Text(
            '${expense ? '−' : '+'}${_price(purchase.amount, purchase.currency)}',
            style: const TextStyle(fontWeight: FontWeight.w700, color: _ink),
          ),
          children: [
            if (purchase.items.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 12),
                child: Text('No reviewed product lines saved for this entry.',
                    style: TextStyle(color: _muted)),
              )
            else
              ...purchase.items.map((item) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Row(children: [
                  Expanded(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(item.name),
                      Text(item.category,
                          style: const TextStyle(color: _muted, fontSize: 12)),
                    ],
                  )),
                  const SizedBox(width: 12),
                  Text(_price(item.amount, purchase.currency)),
                ]),
              )),
            const SizedBox(height: 5),
          ],
        );
      }).toList(),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          const Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('YOUR MONEY. DECODED.',
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w900,
                      letterSpacing: -1, color: _ink)),
              Text('ACCOUNT TELEMETRY  /  VERIFIED TRANSACTIONS',
                  style: TextStyle(fontSize: 12, color: _muted)),
            ],
          )),
          IconButton(
            tooltip: 'Refresh spending',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded, color: _ink),
          ),
        ]),
        const SizedBox(height: 17),
        Wrap(spacing: 12, runSpacing: 9, children: [
          OutlinedButton.icon(
            onPressed: _loading ? null : _chooseMonth,
            icon: const Icon(Icons.calendar_month_outlined),
            label: Text(_monthTitle(_monthKey)),
          ),
          if (d != null)
            DropdownButton<String>(
              value: d.currencies.contains(_currency) ? _currency : null,
              hint: const Text('Currency'),
              items: d.currencies.map((currency) => DropdownMenuItem(
                value: currency,
                child: Text(currency),
              )).toList(),
              onChanged: _loading ? null : (currency) {
                if (currency == null) return;
                setState(() => _currency = currency);
                _load();
              },
            ),
          FilledButton.icon(
            onPressed: widget.onScan,
            icon: const Icon(Icons.add_a_photo_outlined),
            label: const Text('Scan receipt'),
            style: FilledButton.styleFrom(
              backgroundColor: TerminalColors.phosphor,
              foregroundColor: TerminalColors.background,
            ),
          ),
        ]),
        const SizedBox(height: 20),
        if (_loading && d == null)
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 50),
            child: Center(child: CircularProgressIndicator()),
          ),
        if (_loading && d != null)
          const LinearProgressIndicator(minHeight: 2),
        if (_error != null)
          _panel(Column(
            children: [
              Text(_error!, style: const TextStyle(color: Colors.red)),
              const SizedBox(height: 8),
              TextButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          )),
        if (d != null) ...[
          _hero(d),
          _section('Spending over time', _chart(d),
              subtitle: 'Six-month trend ending in the selected month'),
          LayoutBuilder(
            builder: (context, box) {
              final categories = _section(
                'By product category', _categoryPanel(d),
                subtitle: 'Reviewed item lines, excluding taxes and gaps',
              );
              final products = _section(
                'Top purchased products', _topProducts(d),
                subtitle: 'Receipt line amounts, not unit prices',
              );
              if (box.maxWidth >= 760) {
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: categories),
                    const SizedBox(width: 18),
                    Expanded(child: products),
                  ],
                );
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [categories, products],
              );
            },
          ),
          if (d.pendingCount > 0) _pending(d),
          _section('Recent transactions', _purchases(d),
              subtitle: 'Most recent records across all dates and currencies'),
          if (d.insights.isNotEmpty)
            _section('From your spending', _panel(Column(
              children: d.insights.map((insight) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.tips_and_updates_outlined,
                        size: 18, color: _ink),
                    const SizedBox(width: 10),
                    Expanded(child: Text(insight)),
                  ],
                ),
              )).toList(),
            )), subtitle: 'Calculated from recorded transactions; not AI advice'),
        ],
      ],
    );
  }
}
