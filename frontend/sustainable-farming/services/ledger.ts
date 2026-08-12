import { getInterventionsByPlanting } from "./interventions";
import { getPlantings } from "./plantings";
import type { Intervention, InterventionType } from "../types/models";

export interface LedgerBreakdownItem {
  type: InterventionType;
  label: string;
  total: number;
}

export interface Ledger {
  income: number;
  expense: number;
  netProfit: number;
  /** Null when there's no income yet — nothing to divide by. */
  marginPct: number | null;
  breakdown: LedgerBreakdownItem[];
  transactions: Intervention[];
  /**
   * Per the Updated Wireframe Spec: a pre-harvest negative balance must be
   * labeled "Current Cost of Cultivation", never "Loss".
   */
  isPreHarvest: boolean;
}

const EXPENSE_LABELS: Record<Exclude<InterventionType, "harvest">, string> = {
  chemical: "Fertilizer & Spray",
  labor: "Labor",
  irrigation: "Irrigation",
};

export async function getPlantingLedger(plantingId: string): Promise<Ledger> {
  const transactions = await getInterventionsByPlanting(plantingId);

  const income = sum(transactions.filter((t) => t.type === "harvest"));
  const expenseTypes: Exclude<InterventionType, "harvest">[] = [
    "chemical",
    "labor",
    "irrigation",
  ];
  const breakdown: LedgerBreakdownItem[] = expenseTypes.map((type) => ({
    type,
    label: EXPENSE_LABELS[type],
    total: sum(transactions.filter((t) => t.type === type)),
  }));
  const expense = breakdown.reduce((acc, b) => acc + b.total, 0);
  const netProfit = income - expense;

  return {
    income,
    expense,
    netProfit,
    marginPct: income > 0 ? (netProfit / income) * 100 : null,
    breakdown,
    transactions,
    isPreHarvest: income === 0,
  };
}

function sum(items: Intervention[]): number {
  return items.reduce((acc, i) => acc + i.costInInr, 0);
}

export interface SeasonFinancials {
  totalSpent: number;
  totalEarned: number;
}

/** Aggregates every planting's ledger for the Home dashboard's Season Financials widget. */
export async function getSeasonFinancials(): Promise<SeasonFinancials> {
  const plantings = await getPlantings();
  const ledgers = await Promise.all(
    plantings.map((p) => getPlantingLedger(p.id))
  );
  return ledgers.reduce(
    (acc, l) => ({
      totalSpent: acc.totalSpent + l.expense,
      totalEarned: acc.totalEarned + l.income,
    }),
    { totalSpent: 0, totalEarned: 0 }
  );
}
