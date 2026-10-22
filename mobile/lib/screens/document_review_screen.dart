import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../services/document_models.dart';
import '../services/spendwise_api.dart';
import 'draft_review_dialog.dart';
import 'receipt_items_editor.dart';

class DocumentReviewScreen extends StatefulWidget {
  const DocumentReviewScreen({
    super.key,
    this.initialReceiptBytes,
    this.initialReceiptFilename,
  });

  final Uint8List? initialReceiptBytes;
  final String? initialReceiptFilename;

  @override
  State<DocumentReviewScreen> createState() => _DocumentReviewScreenState();
}

class _DocumentReviewScreenState extends State<DocumentReviewScreen> {
  final _api = SpendwiseApi();

  String? _filename;
  Uint8List? _selectedBytes;
  String? _documentId;

  List<TransactionDraftRecord> _drafts = [];

  bool _busy = false;
  String? _message;
  String? _error;

  @override
  void initState() {
    super.initState();

    final image = widget.initialReceiptBytes;
    if (image == null) return;

    _filename = widget.initialReceiptFilename ?? 'receipt.jpg';
    _selectedBytes = image;

    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;

      _run(() async {
        // Both calls use the current authenticated FastAPI client.
        await _upload();
        await _prepare();
      });
    });
  }

  @override
  void dispose() {
    _api.dispose();
    super.dispose();
  }

  Future<void> _run(Future<void> Function() action) async {
    if (_busy) return;

    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await action();
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = error is ApiException
              ? error.message
              : 'Operation failed. Please try again.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _busy = false);
      }
    }
  }

  Future<void> _pickFile() async {
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png'],
    );

    if (file == null) return;

    final length = file.lengthSync() ?? await file.length();

    if (length != null && length > SpendwiseApi.maxDocumentBytes) {
      throw ApiException(413, 'File exceeds the 5 MB limit.');
    }

    final bytes = await file.readAsBytes();

    if (bytes.isEmpty || bytes.length > SpendwiseApi.maxDocumentBytes) {
      throw ApiException(413, 'Select a nonempty file under 5 MB.');
    }

    if (!mounted) return;

    setState(() {
      _filename = file.name;
      _selectedBytes = bytes;
      _documentId = null;
      _drafts = [];
      _message = 'File selected. Review and upload.';
    });
  }

  Future<void> _upload() async {
    if (_filename == null || _selectedBytes == null) {
      return;
    }

    final result = await _api.uploadDocument(
      filename: _filename!,
      bytes: _selectedBytes!,
    );

    if (!mounted) return;

    setState(() {
      _documentId = result.id;
      _selectedBytes = null;
      _drafts = [];
      _message =
          'Uploaded: ${result.filename} '
          '(${result.status})';
    });
  }

  Future<void> _fetchDrafts() async {
    final id = _documentId;
    if (id == null) return;

    final result = await _api.getDrafts(id);

    if (!mounted) return;

    setState(() {
      _drafts = result;
      _message = '${result.length} draft(s) loaded.';
    });
  }

  Future<void> _prepare() async {
    final id = _documentId;
    if (id == null) return;

    try {
      final result = await _api.prepareDocument(id);

      if (!mounted) return;

      setState(() {
        _drafts = result;
        _message = 'AI extraction ready for review.';
      });
    } on ApiException catch (error) {
      if (error.statusCode == 409 &&
          error.message.contains('already prepared')) {
        await _fetchDrafts();
      } else {
        rethrow;
      }
    }
  }

  Future<void> _approve(TransactionDraftRecord draft) async {
    final corrected = await showDraftEditDialog(context, draft);

    if (corrected == null || !mounted) return;

    bool confirmSimilar = false;
    bool confirmItemMismatch = false;
    bool approved = false;
    await _run(() async {
      while (true) {
        try {
          await _api.approveDraft(
            draft.id,
            corrected,
            confirmSimilar: confirmSimilar,
            confirmItemMismatch: confirmItemMismatch,
          );
          break;
        } on ApiException catch (error) {
          if (error.statusCode != 409) rethrow;

          final isDuplicate = error.message.contains('Possible duplicate');

          final isItemMismatch = error.message.contains(
            'Receipt item subtotal mismatch',
          );

          if (!isDuplicate && !isItemMismatch) {
            rethrow;
          }

          if (!mounted) return;

          final confirmed = await showDialog<bool>(
            context: context,
            builder: (dialogContext) => AlertDialog(
              title: Text(
                isDuplicate ? 'Possible duplicate' : 'Item subtotal mismatch',
              ),
              content: Text(
                isDuplicate
                    ? 'A similar transaction exists. '
                          'Confirm this is a separate purchase.'
                    : 'The sum of reviewed items differs '
                          'from the receipt subtotal. '
                          'Check the original receipt before '
                          'confirming.',
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext, false),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(dialogContext, true),
                  child: const Text('Confirm'),
                ),
              ],
            ),
          );

          if (confirmed != true) return;

          if (isDuplicate) {
            confirmSimilar = true;
          } else {
            confirmItemMismatch = true;
          }
        }
      }
      approved = true;
      await _fetchDrafts();
    });
    if (approved && mounted && widget.initialReceiptBytes != null) {
      final nextAction = await showModalBottomSheet<String>(
        context: context,
        showDragHandle: true,
        builder: (sheetContext) => SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(
                  Icons.check_circle_rounded,
                  size: 56,
                  color: Color(0xFF237B65),
                ),
                const SizedBox(height: 12),
                const Text(
                  'Receipt saved!',
                  style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => Navigator.pop(sheetContext, 'scan'),
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('Scan another'),
                  ),
                ),
                TextButton(
                  onPressed: () => Navigator.pop(sheetContext, 'dashboard'),
                  child: const Text('Go to dashboard'),
                ),
              ],
            ),
          ),
        ),
      );

      if (mounted && nextAction != null) {
        Navigator.pop(context, nextAction);
      }
    }
  }

  Future<void> _reject(TransactionDraftRecord draft) async {
    final reason = await showRejectDialog(context);

    if (reason == null || !mounted) return;

    await _run(() async {
      await _api.rejectDraft(draft.id, reason);
      await _fetchDrafts();
    });
  }

  Future<void> _suggestAndReview(TransactionDraftRecord draft) async {
    await _run(() async {
      final suggestions = await _api.suggestDraftCategories(draft.id);
      if (!mounted) return;
      final overrides = <int, String>{};
      for (final suggestion in suggestions) {
        final index = suggestion['line_index'];
        final category = suggestion['category'];
        if (index is int && category is String && category.isNotEmpty) {
          overrides[index] = category;
        }
      }
      final edited = await showDialog<List<Map<String, dynamic>>>(
        context: context,
        builder: (_) => ReceiptItemsEditor(
          initialItems: draft.receiptItems,
          suggestedCategories: overrides,
        ),
      );
      if (edited == null || !mounted) return;
      await _api.saveDraftItems(draft.id, edited);
      await _fetchDrafts();
    });
  }

  bool get _isReceipt {
    final name = (_filename ?? '').toLowerCase();

    return name.endsWith('.jpg') ||
        name.endsWith('.jpeg') ||
        name.endsWith('.png');
  }

  Future<void> _editReceiptItems(TransactionDraftRecord draft) async {
    final edited = await showDialog<List<Map<String, dynamic>>>(
      context: context,
      builder: (_) => ReceiptItemsEditor(initialItems: draft.receiptItems),
    );

    if (edited == null || !mounted) return;

    await _run(() async {
      await _api.saveDraftItems(draft.id, edited);

      await _fetchDrafts();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          widget.initialReceiptBytes != null
              ? 'Review your receipt'
              : 'Document Review',
        ),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              if (widget.initialReceiptBytes != null) ...[
                ClipRRect(
                  borderRadius: BorderRadius.circular(20),
                  child: Image.memory(
                    widget.initialReceiptBytes!,
                    height: 220,
                    fit: BoxFit.contain,
                  ),
                ),
                const SizedBox(height: 16),
                const Text(
                  'Check the merchant, total and purchased items '
                  'against your photo before approving.',
                ),
                const SizedBox(height: 20),
              ],
              Text(
                'Upload a fictional receipt or statement',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              const Text(
                'Supported: PDF, JPG, JPEG, PNG. '
                'Maximum file size: 5 MB.',
              ),
              const SizedBox(height: 12),
              if (widget.initialReceiptBytes == null) ...[
                OutlinedButton.icon(
                  onPressed: _busy ? null : () => _run(_pickFile),
                  icon: const Icon(Icons.attach_file),
                  label: const Text('Choose File'),
                ),

                if (_filename != null)
                  Padding(
                    padding: const EdgeInsets.all(8),
                    child: Text('Selected: $_filename'),
                  ),

                FilledButton.icon(
                  onPressed: _busy || _selectedBytes == null
                      ? null
                      : () => _run(_upload),
                  icon: const Icon(Icons.cloud_upload),
                  label: const Text('Upload Document'),
                ),
              ],
              if (_documentId != null) ...[
                const SizedBox(height: 16),
                SelectableText('Document ID: $_documentId'),
                const SizedBox(height: 12),
                FilledButton.icon(
                  onPressed: _busy ? null : () => _run(_prepare),
                  icon: const Icon(Icons.auto_awesome),
                  label: const Text('Extract and Prepare Drafts'),
                ),
                TextButton(
                  onPressed: _busy ? null : () => _run(_fetchDrafts),
                  child: const Text('Reload Existing Drafts'),
                ),
              ],

              if (_busy) const LinearProgressIndicator(),

              if (_message != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(_message!),
                ),

              if (_error != null)
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),

              if (_drafts.isNotEmpty) ...[
                const SizedBox(height: 24),
                Text(
                  'AI Transaction Drafts',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
              ],

              ..._drafts.map(
                (draft) => Card(
                  margin: const EdgeInsets.symmetric(vertical: 6),
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          draft.merchant ?? 'Unknown merchant',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          '${draft.currency ?? "Unknown currency"} '
                          '${draft.amount ?? "Unknown amount"}',
                        ),
                        Text(
                          'Date: '
                          '${draft.transactionDate ?? "Missing"}',
                        ),
                        Text(
                          'Direction: '
                          '${draft.direction ?? "Unknown"}',
                        ),
                        Text('Status: ${draft.status}'),

                        if (draft.reviewReasons.isNotEmpty)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text(
                              'Review: '
                              '${draft.reviewReasons.join("; ")}',
                            ),
                          ),

                        if (draft.receiptItems.isNotEmpty) ...[
                          const SizedBox(height: 8),

                          const Text(
                            'Purchased items',
                            style: TextStyle(fontWeight: FontWeight.bold),
                          ),

                          ...draft.receiptItems.map(
                            (item) => Text(
                              '${item.name} — '
                              '${item.amount ?? "Unknown"} '
                              '(${item.category})',
                            ),
                          ),
                        ],

                        if (draft.status == 'pending' && _isReceipt)
                          OutlinedButton.icon(
                            onPressed: _busy
                                ? null
                                : () => _editReceiptItems(draft),
                            icon: const Icon(Icons.edit_note),
                            label: Text(
                              draft.itemsReviewed
                                  ? 'Edit reviewed items'
                                  : 'Review purchased items',
                            ),
                          ),

                        if (draft.status == 'pending' && _isReceipt)
                          TextButton.icon(
                            onPressed: _busy
                                ? null
                                : () => _suggestAndReview(draft),
                            icon: const Icon(Icons.auto_fix_high),
                            label: const Text('Suggest categories (ML/Ollama)'),
                          ),

                        if (draft.status == 'pending')
                          Wrap(
                            spacing: 8,
                            children: [
                              FilledButton(
                                onPressed: _busy ? null : () => _approve(draft),
                                child: const Text('Review & Approve'),
                              ),
                              OutlinedButton(
                                onPressed: _busy ? null : () => _reject(draft),
                                child: const Text('Reject'),
                              ),
                            ],
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
