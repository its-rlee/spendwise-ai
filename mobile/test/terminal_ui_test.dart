import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/theme/terminal_theme.dart';
import 'package:mobile/screens/login_screen.dart';

void main() {
  testWidgets('terminal action button remains keyboard/touch accessible',
      (tester) async {
    var presses = 0;
    await tester.pumpWidget(MaterialApp(
      theme: createTerminalTheme(),
      home: Scaffold(
        body: Center(
          child: TerminalActionButton(
            label: 'Activate',
            icon: Icons.bolt,
            onPressed: () => presses++,
          ),
        ),
      ),
    ));
    expect(find.text('ACTIVATE'), findsOneWidget);
    await tester.tap(find.text('ACTIVATE'));
    await tester.pump();
    expect(presses, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets('animated logo and progress render when motion is disabled',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: createTerminalTheme(),
      home: const MediaQuery(
        data: MediaQueryData(disableAnimations: true),
        child: Scaffold(
          body: Column(
            children: [
              TerminalLogo(size: 48),
              TerminalLoading(label: 'EXTRACTING'),
            ],
          ),
        ),
      ),
    ));
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.byType(TerminalLogo), findsOneWidget);
    expect(find.text('EXTRACTING'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  for (final size in [const Size(390, 844), const Size(1280, 820)]) {
    testWidgets('login adapts without overflow at ${size.width}px',
        (tester) async {
      await tester.binding.setSurfaceSize(size);
      addTearDown(() => tester.binding.setSurfaceSize(null));
      await tester.pumpWidget(MaterialApp(
        theme: createTerminalTheme(),
        home: const LoginScreen(),
      ));
      await tester.pump(const Duration(milliseconds: 30));
      expect(find.text('ESTABLISH CONNECTION'), findsOneWidget);
      expect(find.byType(TextFormField), findsNWidgets(2));
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('terminal atmosphere does not steal button taps',
      (tester) async {
    var taps = 0;
    await tester.pumpWidget(MaterialApp(
      home: Stack(
        children: [
          Scaffold(body: Center(child: TextButton(
            onPressed: () => taps++,
            child: const Text('Tap through'),
          ))),
          const Positioned.fill(child: TerminalAtmosphere()),
        ],
      ),
    ));
    await tester.tap(find.text('Tap through'));
    expect(taps, 1);
  });
}
