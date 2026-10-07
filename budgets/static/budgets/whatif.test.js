const assert = require("assert");
const path = require("path");
const w = require(path.join(__dirname, "whatif.js"));

const base = {
  balanceOre: 12000000,
  rateMicro: 30000,
  amortMicro: 20000,
  incomes: [
    { person: "Person 1", ore: 1000000 },
    { person: "Person 2", ore: 800000 },
    { person: "", ore: 50000 },
  ],
  expenses: [
    { category: "Transport", ore: 10000 },
    { category: "Leva", ore: 200000 },
    { category: "Lån", ore: 30000 },
  ],
  categoryOrder: ["Boende", "Transport", "Leva", "Lån", "Sparande", "Övrigt"],
};

const saved = w.evaluate(base, w.savedControls(base));
assert.strictEqual(saved.interestOre, 30000n);
assert.strictEqual(saved.amortOre, 20000n);
assert.strictEqual(saved.incomeOre, 1850000n);
assert.strictEqual(saved.expenseOre, 290000n);
assert.strictEqual(saved.leftOre, 1560000n);
assert.strictEqual(saved.categories[0].category, "Boende");
assert.strictEqual(saved.categories[0].ore, 50000n);
assert.strictEqual(w.formatKr(saved.leftOre), "15 600 kr");
assert.strictEqual(w.deltaText(0n), "Samma kvar som sparat");
assert.strictEqual(w.formatPercent(saved.leftOre, saved.incomeOre), "84,3 %");

const dearer = w.savedControls(base);
dearer.rateMicro = 40000;
const atFour = w.evaluate(base, dearer);
assert.strictEqual(atFour.interestOre, 40000n);
assert.strictEqual(atFour.leftOre, 1550000n);
assert.strictEqual(w.deltaText(atFour.leftOre - saved.leftOre), "100 kr mindre kvar än sparat");

const groceries = w.savedControls(base);
groceries.expenseScale.Leva = 150;
const leva = w.evaluate(base, groceries);
assert.strictEqual(leva.expenseOre, 390000n);
assert.strictEqual(leva.leftOre, 1460000n);
assert.strictEqual(w.deltaText(leva.leftOre - saved.leftOre), "1 000 kr mindre kvar än sparat");
assert.strictEqual(leva.categories.find((row) => row.category === "Leva").ore, 300000n);
assert.strictEqual(leva.categories.find((row) => row.category === "Boende").ore, 50000n);

const halfPay = w.savedControls(base);
halfPay.incomeScale["Person 1"] = 50;
const halved = w.evaluate(base, halfPay);
assert.strictEqual(halved.incomeOre, 1350000n);
assert.strictEqual(halved.leftOre, 1060000n);
assert.strictEqual(w.deltaText(halved.leftOre - saved.leftOre), "5 000 kr mindre kvar än sparat");

assert.strictEqual(w.monthlyOre(10000, 10000), 8n);
assert.strictEqual(w.monthlyOre(100, 100000), 1n);
assert.strictEqual(w.monthlyOre(6000000, 1), 1n);
assert.strictEqual(w.scaleOre(1, 50), 1n);
assert.strictEqual(w.formatKr(8n), "0,08 kr");
assert.strictEqual(w.formatKr(-1560000n), "-15 600 kr");
assert.strictEqual(w.formatRate(30000), "3 %");
assert.strictEqual(w.formatRate(35500), "3,55 %");
assert.strictEqual(w.formatRate(35525), "3,5525 %");
assert.strictEqual(w.formatRate(80500), "8,05 %");
assert.strictEqual(w.formatPercent(-100n, 300n), "-33,3 %");
assert.strictEqual(w.formatPercent(1n, 16n), "6,3 %");
assert.strictEqual(w.formatPercent(0n, 0n), "–");
assert.strictEqual(w.barPct(1n, 3n), 33);

const cleared = {
  balanceOre: 120000,
  rateMicro: 0,
  amortMicro: 1000000,
  incomes: [],
  expenses: [],
  categoryOrder: base.categoryOrder,
};
const paid = w.evaluate(cleared, w.savedControls(cleared));
assert.strictEqual(paid.amortOre, 10000n);
assert.strictEqual(paid.year.balanceOre, 0n);
assert.strictEqual(paid.year.clearsDebt, true);
assert.strictEqual(paid.year.leftOre, -120000n);

const span = w.rateRange(30000);
assert.strictEqual(span.min, 0);
assert.strictEqual(span.value, 30000);
assert.strictEqual(span.step, 100);
assert.ok(span.max >= 80000);
assert.strictEqual(span.max % 100, 0);

console.log("ok");
