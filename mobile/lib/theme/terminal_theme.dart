import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Original retro-science interface inspired by vintage monochrome instruments.
/// No Fallout artwork, brand assets, or proprietary fonts are used.
abstract final class TerminalColors {
  static const background = Color(0xFF06110C);
  static const panel = Color(0xFF0D2016);
  static const raised = Color(0xFF143021);
  static const phosphor = Color(0xFFB7FFAB);
  static const bright = Color(0xFFE0FFE0);
  static const soft = Color(0xFF79C991);
  static const muted = Color(0xFF82A88B);
  static const border = Color(0xFF376B48);
  static const amber = Color(0xFFFFD17A);
  static const danger = Color(0xFFFF9686);
}

ThemeData createTerminalTheme() {
  const colors = TerminalColors;
  final base = ThemeData.dark(useMaterial3: true);
  const round = BorderRadius.all(Radius.circular(12));
  final fieldBorder = OutlineInputBorder(
    borderRadius: round,
    borderSide: const BorderSide(color: TerminalColors.border),
  );
  return base.copyWith(
    scaffoldBackgroundColor: TerminalColors.background,
    colorScheme: const ColorScheme.dark(
      primary: TerminalColors.phosphor,
      onPrimary: TerminalColors.background,
      secondary: TerminalColors.amber,
      onSecondary: TerminalColors.background,
      surface: TerminalColors.panel,
      onSurface: TerminalColors.bright,
      error: TerminalColors.danger,
      onError: TerminalColors.background,
    ),
    textTheme: base.textTheme.apply(
      fontFamily: 'monospace',
      bodyColor: TerminalColors.bright,
      displayColor: TerminalColors.phosphor,
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: TerminalColors.background,
      foregroundColor: TerminalColors.phosphor,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: TextStyle(
        fontFamily: 'monospace',
        fontWeight: FontWeight.w900,
        fontSize: 19,
        letterSpacing: 1.5,
        color: TerminalColors.phosphor,
      ),
    ),
    cardTheme: CardThemeData(
      color: TerminalColors.panel,
      elevation: 0,
      margin: const EdgeInsets.symmetric(vertical: 6),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(15),
        side: const BorderSide(color: TerminalColors.border),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: TerminalColors.panel,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: TerminalColors.border),
      ),
    ),
    dividerTheme: const DividerThemeData(
      color: TerminalColors.border,
      thickness: 1,
      space: 20,
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: TerminalColors.raised,
      labelStyle: const TextStyle(color: TerminalColors.soft),
      hintStyle: const TextStyle(color: TerminalColors.muted),
      floatingLabelStyle: const TextStyle(color: TerminalColors.phosphor),
      border: fieldBorder,
      enabledBorder: fieldBorder,
      focusedBorder: fieldBorder.copyWith(
        borderSide: const BorderSide(color: TerminalColors.phosphor, width: 1.6),
      ),
      errorBorder: fieldBorder.copyWith(
        borderSide: const BorderSide(color: TerminalColors.danger),
      ),
      focusedErrorBorder: fieldBorder.copyWith(
        borderSide: const BorderSide(color: TerminalColors.danger, width: 1.6),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        minimumSize: const Size(48, 50),
        foregroundColor: TerminalColors.background,
        backgroundColor: TerminalColors.phosphor,
        disabledBackgroundColor: TerminalColors.border,
        disabledForegroundColor: TerminalColors.muted,
        textStyle: const TextStyle(
          fontWeight: FontWeight.w900, fontFamily: 'monospace', letterSpacing: 0.8,
        ),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(11)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        minimumSize: const Size(48, 50),
        foregroundColor: TerminalColors.phosphor,
        side: const BorderSide(color: TerminalColors.border),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(11)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        minimumSize: const Size(48, 44),
        foregroundColor: TerminalColors.phosphor,
      ),
    ),
    iconTheme: const IconThemeData(color: TerminalColors.phosphor),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: TerminalColors.phosphor,
      linearTrackColor: TerminalColors.raised,
    ),
    snackBarTheme: SnackBarThemeData(
      backgroundColor: TerminalColors.raised,
      contentTextStyle: const TextStyle(color: TerminalColors.bright),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
      behavior: SnackBarBehavior.floating,
    ),
  );
}

/// Thin lines and engineering corner marks. Purely decorative and never interactive.
class TerminalAtmosphere extends StatelessWidget {
  const TerminalAtmosphere({super.key});

  @override
  Widget build(BuildContext context) {
    return const IgnorePointer(
      child: ExcludeSemantics(
        child: RepaintBoundary(
          child: CustomPaint(
            painter: _AtmospherePainter(),
            size: Size.infinite,
          ),
        ),
      ),
    );
  }
}

class _AtmospherePainter extends CustomPainter {
  const _AtmospherePainter();

  @override
  void paint(Canvas canvas, Size size) {
    final line = Paint()
      ..color = TerminalColors.phosphor.withValues(alpha: 0.038)
      ..strokeWidth = 1;
    for (var y = 3.0; y < size.height; y += 7) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }
    final border = Paint()
      ..color = TerminalColors.phosphor.withValues(alpha: 0.24)
      ..strokeWidth = 1.2
      ..style = PaintingStyle.stroke;
    const corner = 16.0;
    const pad = 10.0;
    final path = Path()
      ..moveTo(pad, pad + corner)..lineTo(pad, pad)..lineTo(pad + corner, pad)
      ..moveTo(size.width - pad - corner, pad)
      ..lineTo(size.width - pad, pad)
      ..lineTo(size.width - pad, pad + corner)
      ..moveTo(pad, size.height - pad - corner)
      ..lineTo(pad, size.height - pad)
      ..lineTo(pad + corner, size.height - pad)
      ..moveTo(size.width - pad - corner, size.height - pad)
      ..lineTo(size.width - pad, size.height - pad)
      ..lineTo(size.width - pad, size.height - pad - corner);
    canvas.drawPath(path, border);
  }

  @override
  bool shouldRepaint(covariant _AtmospherePainter oldDelegate) => false;
}

class TerminalPanel extends StatelessWidget {
  const TerminalPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(20),
    this.glow = false,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final bool glow;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: TerminalColors.panel,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(
          color: glow ? TerminalColors.soft : TerminalColors.border,
        ),
        boxShadow: glow
            ? [BoxShadow(
                color: TerminalColors.phosphor.withValues(alpha: 0.13),
                blurRadius: 20,
                spreadRadius: 1,
              )]
            : null,
      ),
      child: child,
    );
  }
}

class TerminalSectionTitle extends StatelessWidget {
  const TerminalSectionTitle(this.label, {super.key, this.index});
  final String label;
  final String? index;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        if (index != null) ...[
          Text('$index /', style: const TextStyle(
            color: TerminalColors.amber, fontSize: 12, letterSpacing: 1.5,
          )),
          const SizedBox(width: 10),
        ],
        Flexible(
          child: Text(label.toUpperCase(), style: const TextStyle(
            fontSize: 15,
            letterSpacing: 1.4,
            fontWeight: FontWeight.bold,
            color: TerminalColors.phosphor,
          )),
        ),
        const SizedBox(width: 12),
        const Flexible(
          child: Divider(color: TerminalColors.border),
        ),
      ],
    );
  }
}

/// Animated, original scanner insignia; animation honors reduce-motion.
class TerminalLogo extends StatefulWidget {
  const TerminalLogo({super.key, this.size = 64, this.showName = true});
  final double size;
  final bool showName;

  @override
  State<TerminalLogo> createState() => _TerminalLogoState();
}

class _TerminalLogoState extends State<TerminalLogo>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 4),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.of(context).disableAnimations) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'SpendWise AI',
      child: ExcludeSemantics(
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedBuilder(
              animation: _controller,
              builder: (context, child) {
                final pulse = 0.65 + 0.35 *
                    math.sin(_controller.value * 2 * math.pi).abs();
                return Container(
                  width: widget.size,
                  height: widget.size,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: TerminalColors.phosphor.withValues(alpha: pulse),
                      width: 1.5,
                    ),
                    boxShadow: [BoxShadow(
                      color: TerminalColors.phosphor.withValues(alpha: 0.1 * pulse),
                      blurRadius: 18,
                    )],
                  ),
                  child: Stack(
                    alignment: Alignment.center,
                    children: [
                      Icon(Icons.receipt_long_outlined,
                          size: widget.size * 0.48,
                          color: TerminalColors.phosphor),
                      Transform.rotate(
                        angle: _controller.value * math.pi * 2,
                        child: Icon(Icons.radar,
                            size: widget.size * 0.94,
                            color: TerminalColors.soft.withValues(alpha: 0.6)),
                      ),
                    ],
                  ),
                );
              },
            ),
            if (widget.showName) ...[
              const SizedBox(width: 12),
              const Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('SPENDWISE', style: TextStyle(
                    color: TerminalColors.phosphor,
                    fontWeight: FontWeight.w900,
                    letterSpacing: 2.8,
                    fontSize: 17,
                  )),
                  Text('FINANCIAL INSTRUMENTS // AI', style: TextStyle(
                    color: TerminalColors.muted,
                    letterSpacing: 1.2,
                    fontSize: 8,
                  )),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class TerminalLoading extends StatefulWidget {
  const TerminalLoading({
    super.key,
    this.label = 'PROCESSING',
    this.compact = false,
  });
  final String label;
  final bool compact;

  @override
  State<TerminalLoading> createState() => _TerminalLoadingState();
}

class _TerminalLoadingState extends State<TerminalLoading>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this, duration: const Duration(milliseconds: 1050),
  );

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.of(context).disableAnimations) {
      _controller.stop();
    } else if (!_controller.isAnimating) {
      _controller.repeat();
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: widget.label,
      liveRegion: true,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            for (var i = 0; i < 4; i++)
              Container(
                margin: const EdgeInsets.only(right: 4),
                width: widget.compact ? 5 : 8,
                height: widget.compact ? 12 : 18,
                color: i == (_controller.value * 4).floor()
                    ? TerminalColors.phosphor : TerminalColors.border,
              ),
            const SizedBox(width: 9),
            Flexible(
              child: Text(widget.label, style: const TextStyle(
                color: TerminalColors.phosphor,
                fontSize: 12, fontWeight: FontWeight.w700, letterSpacing: 1.1,
              )),
            ),
          ],
        ),
      ),
    );
  }
}

class TerminalActionButton extends StatefulWidget {
  const TerminalActionButton({
    super.key,
    required this.label,
    required this.icon,
    required this.onPressed,
    this.busy = false,
    this.primary = true,
  });
  final String label;
  final IconData icon;
  final VoidCallback? onPressed;
  final bool busy;
  final bool primary;

  @override
  State<TerminalActionButton> createState() => _TerminalActionButtonState();
}

class _TerminalActionButtonState extends State<TerminalActionButton> {
  bool _hovered = false;
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final enabled = widget.onPressed != null && !widget.busy;
    final active = enabled && _hovered;
    final background = widget.primary
        ? (active ? TerminalColors.bright : TerminalColors.phosphor)
        : (active ? TerminalColors.raised : TerminalColors.panel);
    final foreground = widget.primary
        ? TerminalColors.background : TerminalColors.phosphor;
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: AnimatedScale(
        scale: _pressed && enabled ? 0.975 : 1,
        duration: const Duration(milliseconds: 110),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          constraints: const BoxConstraints(minHeight: 52),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(10),
            color: enabled ? background : TerminalColors.raised,
            border: Border.all(
              color: enabled ? TerminalColors.phosphor : TerminalColors.border,
            ),
            boxShadow: active
                ? [BoxShadow(
                    color: TerminalColors.phosphor.withValues(alpha: 0.25),
                    blurRadius: 16,
                  )]
                : null,
          ),
          child: Material(
            type: MaterialType.transparency,
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: enabled ? widget.onPressed : null,
              onHighlightChanged: (value) {
                if (mounted) setState(() => _pressed = value);
              },
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 20, vertical: 13,
                ),
                child: Center(
                  child: widget.busy
                      ? const TerminalLoading(
                          label: 'PROCESSING', compact: true,
                        )
                      : Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(widget.icon, color: foreground, size: 20),
                            const SizedBox(width: 10),
                            Flexible(
                              child: Text(widget.label.toUpperCase(),
                                textAlign: TextAlign.center,
                                style: TextStyle(
                                  color: enabled ? foreground : TerminalColors.muted,
                                  fontWeight: FontWeight.w900,
                                  letterSpacing: 1,
                                  fontSize: 13,
                                ),
                              ),
                            ),
                          ],
                        ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
