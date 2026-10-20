import 'package:flutter/material.dart';

import '../services/document_models.dart';

Future<Map<String, dynamic>?> showDraftEditDialog(
  BuildContext context,
  TransactionDraftRecord draft,
) {
  return showDialog<Map<String, dynamic>>(
    context: context,
    builder: (dialogContext) => _DraftEditDialog(draft: draft),
  );
}

class _DraftEditDialog extends StatefulWidget {
  const _DraftEditDialog({required this.draft});

  final TransactionDraftRecord draft;

  @override
  State<_DraftEditDialog> createState() => _DraftEditDialogState();
}

class _DraftEditDialogState extends State<_DraftEditDialog> {
  final _formKey = GlobalKey<FormState>();

  late final TextEditingController _merchant;
  late final TextEditingController _amount;
  late final TextEditingController _date;
  late final TextEditingController _currency;
  late final TextEditingController _category;

  String? _direction;

  @override
  void initState() {
    super.initState();

    final draft = widget.draft;

    _merchant = TextEditingController(text: draft.merchant ?? '');
    _amount = TextEditingController(text: draft.amount ?? '');
    _date = TextEditingController(text: draft.transactionDate ?? '');
    _currency = TextEditingController(text: draft.currency ?? '');
    _category = TextEditingController(text: 'Uncategorized');

    _direction = draft.direction == 'debit' || draft.direction == 'credit'
        ? draft.direction
        : null;
  }

  @override
  void dispose() {
    _merchant.dispose();
    _amount.dispose();
    _date.dispose();
    _currency.dispose();
    _category.dispose();
    super.dispose();
  }

  void _confirm() {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    Navigator.pop(context, {
      'merchant': _merchant.text.trim(),
      'amount': _amount.text.trim(),
      'transaction_date': _date.text.trim(),
      'currency': _currency.text.trim().toUpperCase(),
      'direction': _direction,
      'category': _category.text.trim(),
    });
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Review transaction'),
      content: SizedBox(
        width: 420,
        child: SingleChildScrollView(
          child: Form(
            key: _formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextFormField(
                  controller: _merchant,
                  decoration: const InputDecoration(labelText: 'Merchant'),
                  validator: (v) =>
                      (v ?? '').trim().isEmpty ? 'Merchant required' : null,
                ),
                TextFormField(
                  controller: _amount,
                  decoration: const InputDecoration(
                    labelText: 'Amount',
                    hintText: '19.90',
                  ),
                  keyboardType: const TextInputType.numberWithOptions(
                    decimal: true,
                  ),
                  validator: (v) {
                    final text = (v ?? '').trim();

                    if (!RegExp(r'^\d+(\.\d{1,2})?$').hasMatch(text)) {
                      return 'Use a valid amount';
                    }

                    if ((num.tryParse(text) ?? 0) <= 0) {
                      return 'Amount must be positive';
                    }

                    return null;
                  },
                ),
                TextFormField(
                  controller: _date,
                  decoration: const InputDecoration(
                    labelText: 'Date (YYYY-MM-DD)',
                  ),
                  validator: (v) {
                    final text = (v ?? '').trim();
                    if (!RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(text)) {
                      return 'Use YYYY-MM-DD';
                    }

                    final parsed = DateTime.tryParse(text);

                    if (parsed == null ||
                        parsed.year != int.parse(text.substring(0, 4)) ||
                        parsed.month != int.parse(text.substring(5, 7)) ||
                        parsed.day != int.parse(text.substring(8, 10))) {
                      return 'Invalid date';
                    }

                    return null;
                  },
                ),
                TextFormField(
                  controller: _currency,
                  decoration: const InputDecoration(
                    labelText: 'Currency',
                    hintText: 'USD',
                  ),
                  validator: (v) {
                    final text = (v ?? '').trim().toUpperCase();

                    return RegExp(r'^[A-Z]{3}$').hasMatch(text)
                        ? null
                        : 'Enter a 3-letter currency';
                  },
                ),
                DropdownButtonFormField<String>(
                  initialValue: _direction,
                  decoration: const InputDecoration(labelText: 'Direction'),
                  items: const [
                    DropdownMenuItem(
                      value: 'debit',
                      child: Text('Debit (expense)'),
                    ),
                    DropdownMenuItem(
                      value: 'credit',
                      child: Text('Credit (income)'),
                    ),
                  ],
                  onChanged: (value) {
                    setState(() {
                      _direction = value;
                    });
                  },
                  validator: (value) =>
                      value == null ? 'Choose a direction' : null,
                ),
                TextFormField(
                  controller: _category,
                  decoration: const InputDecoration(labelText: 'Category'),
                  validator: (v) =>
                      (v ?? '').trim().isEmpty ? 'Category required' : null,
                ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _confirm,
          child: const Text('Confirm approval'),
        ),
      ],
    );
  }
}

Future<String?> showRejectDialog(BuildContext context) {
  return showDialog<String>(
    context: context,
    builder: (dialogContext) => const _RejectDialog(),
  );
}

class _RejectDialog extends StatefulWidget {
  const _RejectDialog();

  @override
  State<_RejectDialog> createState() => _RejectDialogState();
}

class _RejectDialogState extends State<_RejectDialog> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Reject transaction'),
      content: TextField(
        controller: _controller,
        maxLength: 500,
        decoration: const InputDecoration(
          labelText: 'Reason',
          hintText: 'Transaction not on statement',
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            final reason = _controller.text.trim();

            if (reason.length < 5) return;

            Navigator.pop(context, reason);
          },
          child: const Text('Reject'),
        ),
      ],
    );
  }
}
