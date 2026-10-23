class DashboardItem {
  final String name, category, amount;
  DashboardItem(Map<String, dynamic> json)
      : name = json['name'].toString(),
        category = (json['category'] ?? 'Other').toString(),
        amount = json['amount'].toString();
}
class DashboardPurchase {
  final int id;
  final String merchant, amount, currency, category, direction;
  final String? date;
  final List<DashboardItem> items;
  DashboardPurchase(Map<String, dynamic> j)
      : id = j['id'] as int,
        merchant = j['merchant'].toString(),
        amount = j['amount'].toString(),
        currency = j['currency'].toString(),
        category = j['category'].toString(),
        direction = j['direction'].toString(),
        date = j['date']?.toString(),
        items = (j['items'] as List).map((x) => DashboardItem(Map<String, dynamic>.from(x as Map))).toList();
}
class DashboardMonth {
  final String month, expenses, income;
  DashboardMonth(Map<String, dynamic> j)
      : month = j['month'].toString(),
        expenses = j['expenses'].toString(),
        income = j['income'].toString();
}
class DashboardCategory {
  final String category, amount;
  DashboardCategory(Map<String, dynamic> j)
      : category = j['category'].toString(),
        amount = j['amount'].toString();
}
class PendingReceipt {
  final String id, filename, status;
  PendingReceipt(Map<String, dynamic> j)
      : id = j['id'].toString(),
        filename = j['filename'].toString(),
        status = j['status'].toString();
}
class SpendingDashboard {
  final String currency, month, comparisonBasis, expenses, income, net, lastExpenses, samePointLastExpenses;
  final List<String> currencies, insights;
  final List<DashboardMonth> monthly;
  final List<DashboardCategory> categories;
  final List<DashboardItem> topItems;
  final List<DashboardPurchase> purchases;
  final List<PendingReceipt> pending;
  final int pendingCount;
  SpendingDashboard(Map<String, dynamic> j)
      : currency = j['currency'].toString(),
        month = j['month'].toString(),
        comparisonBasis = j['comparison_basis'].toString(),
        expenses = j['this_month_expenses'].toString(),
        income = j['this_month_income'].toString(),
        net = j['this_month_net'].toString(),
        lastExpenses = j['last_month_expenses'].toString(),
        samePointLastExpenses = j['same_point_last_month_expenses'].toString(),
        currencies = List<String>.from(j['available_currencies'] as List),
        insights = List<String>.from(j['insights'] as List),
        monthly = (j['monthly'] as List).map((x) => DashboardMonth(Map<String, dynamic>.from(x as Map))).toList(),
        categories = (j['item_categories'] as List).map((x) => DashboardCategory(Map<String, dynamic>.from(x as Map))).toList(),
        topItems = (j['top_items'] as List).map((x) => DashboardItem(Map<String, dynamic>.from(x as Map))).toList(),
        purchases = (j['recent_purchases'] as List).map((x) => DashboardPurchase(Map<String, dynamic>.from(x as Map))).toList(),
        pending = (j['pending_receipts'] as List).map((x) => PendingReceipt(Map<String, dynamic>.from(x as Map))).toList(),
        pendingCount = j['pending_receipt_count'] as int;
}
