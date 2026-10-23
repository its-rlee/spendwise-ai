import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../services/dashboard_models.dart';
import '../services/spendwise_api.dart';
import '../theme/terminal_theme.dart';
import 'dashboard_overview.dart';
import 'document_review_screen.dart';
import 'scan_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _api = SpendwiseApi();
  final _question = TextEditingController();
  final List<Map<String, String>> _chat = [];
  int _dashboardRevision = 0;
  bool _asking = false;
  String? _assistantError;
  AssistantReply? _reply;

  @override
  void initState() {
    super.initState();
    // Scan-first on Android; browsers expose the dashboard and a camera
    // activation button to satisfy webcam permission gesture requirements.
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

  Future<void> _openScanner() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const ScanScreen()),
    );
    _refreshDashboard();
  }

  Future<void> _openUpload() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const DocumentReviewScreen()),
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
    final question = _question.text.trim();
    if (question.isEmpty || _asking) return;
    final context = _chat.length <= 6
        ? List<Map<String, String>>.from(_chat)
        : _chat.sublist(_chat.length - 6);
    setState(() {
      _asking = true;
      _assistantError = null;
      _reply = null;
    });
    try {
      final result = await _api.askAssistant(question, history: context);
      if (!mounted) return;
      setState(() {
        _chat.add({'role': 'user', 'content': question});
        _chat.add({'role': 'assistant', 'content': result.answer});
        if (_chat.length > 20) _chat.removeRange(0, _chat.length - 20);
        _reply = result;
        _question.clear();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _assistantError = error is ApiException
            ? error.message : 'AI connection failed. Retry your request.';
      });
    } finally {
      if (mounted) setState(() => _asking = false);
    }
  }

  Widget _assistantPanel() => TerminalPanel(
    padding: const EdgeInsets.all(19),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const TerminalSectionTitle('Financial analyst', index: 'AI'),
        const SizedBox(height: 12),
        const Text(
          'ASK ABOUT PRODUCTS, HISTORY, MERCHANTS, OR TRENDS.',
          style: TextStyle(color: TerminalColors.muted,
              fontSize: 11, letterSpacing: 0.6, height: 1.6),
        ),
        const SizedBox(height: 16),
        if (_chat.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: TerminalColors.raised,
              borderRadius: BorderRadius.circular(9),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.auto_awesome_outlined,
                    color: TerminalColors.amber, size: 23),
                SizedBox(height: 8),
                Text('ANALYST READY', style: TextStyle(
                  color: TerminalColors.phosphor,
                  fontSize: 13, letterSpacing: 1.1,
                )),
                SizedBox(height: 7),
                Text(
                  'Try "What did I buy at Costco?" or '
                  '"Compare my spending by month."',
                  style: TextStyle(
                    color: TerminalColors.muted,
                    height: 1.5, fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ..._chat.map((message) {
          final fromUser = message['role'] == 'user';
          return Align(
            alignment: fromUser ? Alignment.centerRight : Alignment.centerLeft,
            child: Container(
              constraints: const BoxConstraints(maxWidth: 560),
              padding: const EdgeInsets.all(13),
              margin: const EdgeInsets.only(bottom: 9),
              decoration: BoxDecoration(
                color: fromUser ? TerminalColors.raised : TerminalColors.panel,
                borderRadius: BorderRadius.circular(9),
                border: Border.all(
                  color: fromUser
                      ? TerminalColors.soft : TerminalColors.border,
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(fromUser ? 'YOU / INPUT' : 'SPENDWISE / VERIFIED DATA',
                    style: const TextStyle(
                      color: TerminalColors.amber,
                      letterSpacing: 1,
                      fontSize: 9,
                    )),
                  const SizedBox(height: 7),
                  SelectableText(message['content'] ?? '',
                    style: const TextStyle(
                      color: TerminalColors.bright, height: 1.45,
                    )),
                ],
              ),
            ),
          );
        }),
        if (_reply != null)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: const Text('INSPECT DATABASE FACTS',
              style: TextStyle(
                fontSize: 11, letterSpacing: 1,
                color: TerminalColors.soft,
              )),
            children: [
              SelectableText(
                const JsonEncoder.withIndent('  ').convert(_reply!.facts),
                style: const TextStyle(
                  color: TerminalColors.muted, fontSize: 10,
                ),
              ),
            ],
          ),
        if (_assistantError != null) ...[
          const SizedBox(height: 12),
          Text(_assistantError!, style: const TextStyle(
            color: TerminalColors.danger,
          )),
        ],
        const SizedBox(height: 15),
        TextField(
          controller: _question,
          minLines: 1,
          maxLines: 4,
          textInputAction: TextInputAction.send,
          decoration: const InputDecoration(
            hintText: 'Ask a financial question...',
            prefixIcon: Icon(Icons.keyboard_command_key_rounded),
          ),
          onSubmitted: (_) => _askAssistant(),
        ),
        const SizedBox(height: 12),
        TerminalActionButton(
          label: 'Run analysis',
          icon: Icons.bolt_outlined,
          onPressed: _asking ? null : _askAssistant,
          busy: _asking,
        ),
        if (_chat.isNotEmpty) ...[
          const SizedBox(height: 6),
          TextButton.icon(
            onPressed: _asking ? null : () => setState(() {
              _chat.clear();
              _reply = null;
              _assistantError = null;
            }),
            icon: const Icon(Icons.delete_outline),
            label: const Text('Clear conversation'),
          ),
        ],
        const SizedBox(height: 12),
        const Text(
          'Answers use saved approved records. Questions and recent chat '
          'context may be sent to the configured AI provider.',
          style: TextStyle(
            fontSize: 10, color: TerminalColors.muted, height: 1.5,
          ),
        ),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final email = Supabase.instance.client.auth.currentUser?.email;
    return Scaffold(
      appBar: AppBar(
        title: TerminalLogo(
          size: 36,
          showName: MediaQuery.sizeOf(context).width >= 490,
        ),
        actions: [
          IconButton(
            tooltip: 'Upload document',
            icon: const Icon(Icons.upload_file_outlined),
            onPressed: _openUpload,
          ),
          IconButton(
            tooltip: 'Scan receipt',
            icon: const Icon(Icons.center_focus_strong),
            onPressed: _openScanner,
          ),
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => Supabase.instance.client.auth.signOut(),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: SafeArea(
        child: LayoutBuilder(builder: (context, constraints) {
          final wide = constraints.maxWidth >= 1120;
          return SingleChildScrollView(
            padding: EdgeInsets.symmetric(
              horizontal: constraints.maxWidth < 460 ? 16 : 24,
              vertical: 16,
            ),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 1360),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      const Icon(Icons.sensors_outlined,
                          color: TerminalColors.phosphor, size: 16),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text(
                          'DATA LINK ACTIVE  /  ${email ?? "ACCOUNT"}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 10,
                            letterSpacing: 0.8,
                            color: TerminalColors.soft,
                          ),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 23),
                    if (wide)
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            flex: 7,
                            child: DashboardOverview(
                              key: ValueKey(_dashboardRevision),
                              onScan: _openScanner,
                              onResume: _resumeReceipt,
                            ),
                          ),
                          const SizedBox(width: 24),
                          Expanded(flex: 4, child: _assistantPanel()),
                        ],
                      )
                    else ...[
                      DashboardOverview(
                        key: ValueKey(_dashboardRevision),
                        onScan: _openScanner,
                        onResume: _resumeReceipt,
                      ),
                      const SizedBox(height: 24),
                      _assistantPanel(),
                    ],
                    const SizedBox(height: 35),
                    const Center(
                      child: Text(
                        'SPENDWISE // ENGINEERED FOR CLARITY',
                        style: TextStyle(
                          color: TerminalColors.muted,
                          letterSpacing: 2,
                          fontSize: 9,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}
