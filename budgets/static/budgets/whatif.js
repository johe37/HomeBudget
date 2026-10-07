/* Öre-math with round-half-away-from-zero, matching Decimal ROUND_HALF_UP.
   Products can exceed 2^53, so the division uses BigInt. */
(function (root, factory) {
  const api = {};
  factory(api);
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.WhatIf = api;
})(typeof window !== "undefined" ? window : globalThis, function (api) {
  function divRoundHalfAway(numerator, denominator) {
    let n = BigInt(numerator);
    let d = BigInt(denominator);
    if (d < 0n) {
      n = -n;
      d = -d;
    }
    const negative = n < 0n;
    if (negative) n = -n;
    const rounded = (n + d / 2n) / d;
    return negative ? -rounded : rounded;
  }

  function monthlyOre(balanceOre, rateMicro) {
    return divRoundHalfAway(BigInt(balanceOre) * BigInt(rateMicro), 12000000n);
  }

  function scaleOre(ore, percent) {
    return divRoundHalfAway(BigInt(ore) * BigInt(percent), 100n);
  }

  function formatKr(ore) {
    let value = BigInt(ore);
    const negative = value < 0n;
    if (negative) value = -value;
    const whole = (value / 100n).toString();
    const frac = (value % 100n).toString().padStart(2, "0");
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    const body = frac === "00" ? grouped : `${grouped},${frac}`;
    return `${negative ? "-" : ""}${body} kr`;
  }

  function formatRate(micro) {
    let value = BigInt(micro);
    const negative = value < 0n;
    if (negative) value = -value;
    const whole = (value / 10000n).toString();
    const frac = (value % 10000n).toString().padStart(4, "0").replace(/0+$/, "");
    const body = frac ? `${whole},${frac}` : whole;
    return `${negative ? "-" : ""}${body} %`;
  }

  function formatTenths(tenths) {
    let value = BigInt(tenths);
    const negative = value < 0n;
    if (negative) value = -value;
    const whole = (value / 10n).toString();
    const frac = (value % 10n).toString();
    return `${negative ? "-" : ""}${whole},${frac} %`;
  }

  function formatPercent(part, whole) {
    const total = BigInt(whole);
    if (total === 0n) return "–";
    return formatTenths(divRoundHalfAway(BigInt(part) * 1000n, total));
  }

  function barPct(part, whole) {
    const total = BigInt(whole);
    if (total === 0n) return 0;
    return Number(divRoundHalfAway(BigInt(part) * 100n, total));
  }

  function deltaText(deltaOre) {
    const delta = BigInt(deltaOre);
    if (delta === 0n) return "Samma kvar som sparat";
    const amount = formatKr(delta < 0n ? -delta : delta);
    if (delta > 0n) return `${amount} mer kvar än sparat`;
    return `${amount} mindre kvar än sparat`;
  }

  function rateRange(savedMicro) {
    const saved = Number(savedMicro) || 0;
    const step = 100;
    let max = Math.max(saved + 30000, 80000);
    if (max > 1000000) max = 1000000;
    if (saved > max) max = saved;
    const rem = max % step;
    if (rem !== 0) max += step - rem;
    if (max < saved) max = saved;
    return { min: 0, max, step, value: saved };
  }

  function savedControls(baseline) {
    const incomeScale = {};
    for (const row of baseline.incomes || []) incomeScale[row.person] = 100;
    const expenseScale = {};
    for (const row of baseline.expenses || []) expenseScale[row.category] = 100;
    return {
      rateMicro: Number(baseline.rateMicro) || 0,
      amortMicro: Number(baseline.amortMicro) || 0,
      incomeScale,
      expenseScale,
    };
  }

  function evaluate(baseline, controls) {
    const balance = BigInt(baseline.balanceOre || 0);
    const interest = monthlyOre(balance, controls.rateMicro || 0);
    const amort = monthlyOre(balance, controls.amortMicro || 0);
    const incomeScale = controls.incomeScale || {};
    const expenseScale = controls.expenseScale || {};

    let income = 0n;
    const incomes = (baseline.incomes || []).map((row) => {
      const percent = incomeScale[row.person] ?? 100;
      const ore = scaleOre(row.ore, percent);
      income += ore;
      return { person: row.person, ore, percent };
    });

    const byCategory = new Map();
    for (const row of baseline.expenses || []) {
      const percent = expenseScale[row.category] ?? 100;
      const scaled = scaleOre(row.ore, percent);
      byCategory.set(row.category, (byCategory.get(row.category) || 0n) + scaled);
    }
    const mortgage = interest + amort;
    if (mortgage !== 0n) {
      byCategory.set("Boende", (byCategory.get("Boende") || 0n) + mortgage);
    }

    let expense = 0n;
    for (const value of byCategory.values()) expense += value;

    const order = baseline.categoryOrder || [];
    const names = [];
    for (const name of order) {
      if ((byCategory.get(name) || 0n) !== 0n) names.push(name);
    }
    const extras = [...byCategory.keys()]
      .filter((name) => !order.includes(name) && (byCategory.get(name) || 0n) !== 0n)
      .sort((a, b) => a.localeCompare(b, "sv"));
    const categories = [...names, ...extras].map((name) => ({
      category: name,
      ore: byCategory.get(name),
    }));

    const yearAmort = amort * 12n;
    let debt = balance - yearAmort;
    if (debt < 0n) debt = 0n;

    return {
      incomeOre: income,
      expenseOre: expense,
      leftOre: income - expense,
      interestOre: interest,
      amortOre: amort,
      incomes,
      categories,
      year: {
        leftOre: (income - expense) * 12n,
        interestOre: interest * 12n,
        amortOre: yearAmort,
        balanceOre: debt,
        clearsDebt: balance > 0n && yearAmort >= balance,
      },
    };
  }

  api.divRoundHalfAway = divRoundHalfAway;
  api.monthlyOre = monthlyOre;
  api.scaleOre = scaleOre;
  api.formatKr = formatKr;
  api.formatRate = formatRate;
  api.formatPercent = formatPercent;
  api.barPct = barPct;
  api.deltaText = deltaText;
  api.rateRange = rateRange;
  api.savedControls = savedControls;
  api.evaluate = evaluate;
});
