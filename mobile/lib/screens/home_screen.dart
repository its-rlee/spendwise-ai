import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'package:flutter/foundation.dart';

import '../services/spendwise_api.dart';

import 'document_review_screen.dart';

import 'scan_screen.dart';
import 'dashboard_overview.dart';
import '../services/dashboard_models.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _api = SpendwiseApi();

  final _question = TextEditingController(
    text: 'How much did I spend on groceries this month?',
  );

  int _dashboardRevision = 0;
  bool _asking = false;

  String? _assistantError;
  AssistantReply? _reply;
  // Conversation is intentionally held only in memory, not local storage.
  final List<Map<String, String>> _chat = [];

  @override
  void initState() {
    super.initState();


    // After login, launch the receipt scanner on Android.
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _openScanner();
      });
    }
  }

  @override
  void dispose() {
    _api.dispose();
    _question.dispose();
    super.dispose();
  }

  void _refreshDashboard() {
    if (mounted) setState(() => _dashboardRevision++);
  }

  Future<void> _openUpload() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const DocumentReviewScreen(),
      ),
    );
    _refreshDashboard();
  }

  Future<void> _resumeReceipt(PendingReceipt pending) async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => DocumentReviewScreen(
          initialDocumentId: pending.id,
          initialReceiptFilename: pending.filename,
        ),
      ),
    );
    _refreshDashboard();
  }

  Future<void> _askAssistant() async {
    final text = _question.text.trim();
    if (text.isEmpty || _asking) return;

    final context = _chat.length <= 6
        ? List<Map<String, String>>.from(_chat)
        : _chat.sublist(_chat.length - 6);

    setState(() {
      _asking = true;
      _assistantError = null;
      _reply = null;
    });

    try {
      final result = await _api.askAssistant(text, history: context);
      if (!mounted) return;
      setState(() {
        _chat.add({'role': 'user', 'content': text});
        _chat.add({'role': 'assistant', 'content': result.answer});
        // Keep only recent exchanges in this screen.
        if (_chat.length > 20) _chat.removeRange(0, _chat.length - 20);
        _reply = result;
        _question.clear();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _assistantError = error is ApiException
            ? error.message
            : 'Could not answer. Please retry.';
      });
    } finally {
      if (mounted) setState(() => _asking = false);
    }
  }

  Future<void> _openScanner() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const ScanScreen()),
    );
    _refreshDashboard();
  }

  @override
  Widget build(BuildContext context) {
    final email = Supabase.instance.client.auth.currentUser?.email;

    return Scaffold(
      appBar: AppBar(
        title: const Text('SpendWise AI'),
        actions: [
          IconButton(
            tooltip: 'Upload financial document',
            icon: const Icon(Icons.upload_file),
            onPressed: _openUpload,
          ),
          IconButton(
            tooltip: 'Scan receipt',
            icon: const Icon(Icons.document_scanner_outlined),
            onPressed: _openScanner,
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: () async {
              await Supabase.instance.client.auth.signOut();
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 700),
          child: ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Text(
                'Signed in as ${email ?? "User"}',
                style: Theme.of(context).textTheme.bodyMedium,
              ),

              const SizedBox(height: 24),

              DashboardOverview(
                key: ValueKey(_dashboardRevision),
                onScan: _openScanner,
                onResume: _resumeReceipt,
              ),

              const SizedBox(height: 32),

              Row(
                children: [
                  Expanded(
                    child: Text(
                      'Ask SpendWise AI',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _chat.isEmpty || _asking ? null : () {
                      setState(() {
                        _chat.clear();
                        _reply = null;
                        _assistantError = null;
                      });
                    },
                    icon: const Icon(Icons.delete_outline, size: 18),
                    label: const Text('Clear chat'),
                  ),
                ],
              ),
              const Text(
                'Ask follow-up questions about approved purchases. '
                'Financial totals come from your saved data.',
              ),
              const SizedBox(height: 12),
              ..._chat.map((message) {
                final isUser = message['role'] == 'user';
                return Align(
                  alignment: isUser
                      ? Alignment.centerRight
                      : Alignment.centerLeft,
                  child: Container(
                    constraints: const BoxConstraints(maxWidth: 560),
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: isUser
                          ? Theme.of(context).colorScheme.primaryContainer
                          : Theme.of(context).colorScheme.surfaceContainerLow,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: SelectableText(message['content'] ?? ''),
                  ),
                );
              }),

              TextField(
                controller: _question,
                minLines: 1,
                maxLines: 3,
                decoration: const InputDecoration(
                  hintText: 'Ask about your spending',
                  border: OutlineInputBorder(),
                ),
                onSubmitted: (_) => _askAssistant(),
              ),

              const SizedBox(height: 12),

              FilledButton.icon(
                onPressed: _asking ? null : _askAssistant,
                icon: const Icon(Icons.auto_awesome),
                label: Text(_asking ? 'Analyzing...' : 'Ask AI'),
              ),

              if (_asking)
                const Padding(
                  padding: EdgeInsets.all(12),
                  child: LinearProgressIndicator(),
                ),

              if (_assistantError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Text(
                    _assistantError!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),

              if (_reply != null)
                Card(
                  margin: const EdgeInsets.only(top: 16),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Verified query results',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          'Verified financial facts',
                          style: TextStyle(fontWeight: FontWeight.bold),
                        ),
                        SelectableText(
                          const JsonEncoder.withIndent(
                            '  ',
                          ).convert(_reply!.facts),
                        ),
                      ],
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
