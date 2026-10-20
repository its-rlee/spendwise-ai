import 'package:flutter/material.dart';

import '../services/document_models.dart';

class _ItemFields {
  final name = TextEditingController();
  final amount = TextEditingController();
  final category = TextEditingController(text: 'Uncategorized');

  _ItemFields([ReceiptItemDraft? item]) {
    if (item != null) {
      name.text = item.name;
      amount.text = item.amount ?? '';
      category.text = item.category;
    }
  }

  void dispose() {
    name.dispose();
    amount.dispose();
    category.dispose();
  }
}

class ReceiptItemsEditor extends StatefulWidget {
  final List<ReceiptItemDraft> initialItems;

  const ReceiptItemsEditor({super.key, required this.initialItems});

  @override
  State<ReceiptItemsEditor> createState() => _ReceiptItemsEditorState();
}

class _ReceiptItemsEditorState extends State<ReceiptItemsEditor> {
  final _formKey = GlobalKey<FormState>();

  final List<_ItemFields> _rows = [];
  final List<_ItemFields> _removedRows = [];

  @override
  void initState() {
    super.initState();

    for (final item in widget.initialItems) {
      _rows.add(_ItemFields(item));
    }
  }

  @override
  void dispose() {
    for (final row in [..._rows, ..._removedRows]) {
      row.dispose();
    }
    super.dispose();
  }

  void _save() {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    Navigator.pop(
      context,
      _rows.map((row) {
        return <String, dynamic>{
          'name': row.name.text.trim(),
          'amount': row.amount.text.trim(),
          'category': row.category.text.trim(),
        };
      }).toList(),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Review purchased items'),
      content: SizedBox(
        width: 500,
        height: 420,
        child: Column(
          children: [
            const Text(
              'Compare each item with the receipt. '
              'Correct mistakes before approval.',
            ),
            const SizedBox(height: 12),
            Expanded(
              child: Form(
                key: _formKey,
                child: ListView(
                  children: [
                    for (final row in _rows)
                      Card(
                        key: ObjectKey(row),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Column(
                            children: [
                              TextFormField(
                                controller: row.name,
                                decoration: const InputDecoration(
                                  labelText: 'Item name',
                                ),
                                validator: (value) =>
                                    (value ?? '').trim().isEmpty
                                    ? 'Name required'
                                    : null,
                              ),
                              TextFormField(
                                controller: row.amount,
                                decoration: const InputDecoration(
                                  labelText: 'Line amount',
                                  hintText: '4.99',
                                ),
                                validator: (value) {
                                  if (!RegExp(
                                    r'^\d+(\.\d{1,2})?$',
                                  ).hasMatch((value ?? '').trim())) {
                                    return 'Use a valid amount';
                                  }
                                  return null;
                                },
                              ),
                              TextFormField(
                                controller: row.category,
                                decoration: const InputDecoration(
                                  labelText: 'Category',
                                ),
                                validator: (value) =>
                                    (value ?? '').trim().isEmpty
                                    ? 'Category required'
                                    : null,
                              ),
                              Align(
                                alignment: Alignment.centerRight,
                                child: IconButton(
                                  tooltip: 'Remove item',
                                  onPressed: () {
                                    setState(() {
                                      _rows.remove(row);
                                      _removedRows.add(row);
                                    });
                                  },
                                  icon: const Icon(Icons.delete_outline),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    TextButton.icon(
                      onPressed: _rows.length >= 100
                          ? null
                          : () {
                              setState(() {
                                _rows.add(_ItemFields());
                              });
                            },
                      icon: const Icon(Icons.add),
                      label: const Text('Add missing item'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _save,
          child: const Text('Save reviewed items'),
        ),
      ],
    );
  }
}
