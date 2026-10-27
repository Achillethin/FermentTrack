// Self-check for readings.js (no test runner in this frontend): node src/readings.check.mjs
import assert from "node:assert/strict";
import { parseReading, unusualPh } from "./readings.js";

assert.deepEqual(parseReading("5,8", "pH"), { value: 5.8, unusual: false }); // never 5
assert.deepEqual(parseReading(" 4.2 ", "pH"), { value: 4.2, unusual: false });
assert.deepEqual(parseReading("", "pH"), { value: null });
assert.deepEqual(parseReading("abc", "pH"), { error: "Enter a number, e.g. 4.2" });
assert.deepEqual(parseReading("15", "pH"), { error: "pH runs from 0 to 14" });
assert.deepEqual(parseReading("-1", "pH"), { error: "pH runs from 0 to 14" });
assert.deepEqual(parseReading("2.1", "pH"), { value: 2.1, unusual: true });
assert.deepEqual(parseReading("150", "rise"), { value: 150, unusual: false }); // only pH has a scale
assert.match(unusualPh(2.1), /^pH 2\.1\? Most ferments sit between 3 and 7/);
console.log("readings.js ok");
