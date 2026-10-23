import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../theme/terminal_theme.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _loading = false;
  bool _obscured = true;
  String? _error;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _signIn() async {
    if (!_formKey.currentState!.validate() || _loading) return;
    setState(() { _loading = true; _error = null; });
    try {
      await Supabase.instance.client.auth.signInWithPassword(
        email: _email.text.trim(), password: _password.text,
      );
    } on AuthException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } catch (_) {
      if (mounted) setState(() => _error = 'Connection failed. Try again.');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Widget _intro({bool compact = false}) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      TerminalLogo(size: compact ? 52 : 76),
      SizedBox(height: compact ? 30 : 70),
      const Text('PERSONAL FINANCE // 01', style: TextStyle(
        color: TerminalColors.amber, letterSpacing: 2.4,
        fontSize: 11, fontWeight: FontWeight.w800,
      )),
      const SizedBox(height: 15),
      Text('YOUR MONEY.\nDECODED.', style: TextStyle(
        fontSize: compact ? 37 : 58,
        height: 1.06,
        fontWeight: FontWeight.w900,
        color: TerminalColors.phosphor,
        letterSpacing: -2,
      )),
      const SizedBox(height: 18),
      const Text(
        'Scan the paper trail. Verify the numbers. '
        'Know exactly where it all went.',
        style: TextStyle(
          color: TerminalColors.muted,
          height: 1.6,
          fontSize: 14,
        ),
      ),
      const SizedBox(height: 25),
      const Row(children: [
        Icon(Icons.wifi_tethering_outlined,
            size: 15, color: TerminalColors.phosphor),
        SizedBox(width: 8),
        Flexible(child: Text('SECURE DATA LINK  /  SUPABASE AUTH',
            style: TextStyle(
              fontSize: 10, color: TerminalColors.soft, letterSpacing: 1,
            ))),
      ]),
    ],
  );

  Widget _form() => TerminalPanel(
    glow: true,
    padding: const EdgeInsets.all(26),
    child: Form(
      key: _formKey,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const TerminalSectionTitle('Authorized access', index: 'SYS'),
          const SizedBox(height: 15),
          const Text('SIGN IN TO CONTINUE', style: TextStyle(
            fontSize: 12, color: TerminalColors.muted, letterSpacing: 1.2,
          )),
          const SizedBox(height: 24),
          TextFormField(
            controller: _email,
            keyboardType: TextInputType.emailAddress,
            autofillHints: const [AutofillHints.email],
            textInputAction: TextInputAction.next,
            decoration: const InputDecoration(
              labelText: 'EMAIL ADDRESS',
              prefixIcon: Icon(Icons.alternate_email),
            ),
            validator: (value) {
              final email = value?.trim() ?? '';
              return email.contains('@') && email.length >= 5
                  ? null : 'Enter a valid email address';
            },
          ),
          const SizedBox(height: 15),
          TextFormField(
            controller: _password,
            obscureText: _obscured,
            autofillHints: const [AutofillHints.password],
            onFieldSubmitted: (_) => _signIn(),
            decoration: InputDecoration(
              labelText: 'ACCESS PASSWORD',
              prefixIcon: const Icon(Icons.lock_outline),
              suffixIcon: IconButton(
                tooltip: _obscured ? 'Show password' : 'Hide password',
                icon: Icon(
                  _obscured ? Icons.visibility_outlined : Icons.visibility_off_outlined,
                ),
                onPressed: () => setState(() => _obscured = !_obscured),
              ),
            ),
            validator: (value) =>
                (value ?? '').isEmpty ? 'Enter your password' : null,
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            Text(_error!, style: const TextStyle(
              color: TerminalColors.danger, fontSize: 13,
            )),
          ],
          const SizedBox(height: 25),
          TerminalActionButton(
            label: 'Establish connection',
            icon: Icons.login_rounded,
            onPressed: _loading ? null : _signIn,
            busy: _loading,
          ),
          const SizedBox(height: 17),
          const Text(
            'Financial records remain protected by your account. '
            'Verify each AI-extracted receipt before approval.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 11, color: TerminalColors.muted, height: 1.5,
            ),
          ),
        ],
      ),
    ),
  );

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 860;
            return SingleChildScrollView(
              padding: EdgeInsets.symmetric(
                vertical: wide ? 65 : 32, horizontal: 24,
              ),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 1050),
                  child: wide
                      ? Row(
                          crossAxisAlignment: CrossAxisAlignment.center,
                          children: [
                            Expanded(child: _intro()),
                            const SizedBox(width: 75),
                            SizedBox(width: 405, child: _form()),
                          ],
                        )
                      : Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _intro(compact: true),
                            const SizedBox(height: 34),
                            _form(),
                          ],
                        ),
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
