// Offline check of the widget's programme matching (which programme the option cards
// point at after a typed question):  node test_widget.js
const fs = require("fs"), vm = require("vm"), assert = require("assert");

const page = fs.readFileSync(__dirname + "/static/embed.html", "utf8");
const ctx = { document: { addEventListener() {}, getElementById() { return null; } }, parent: { postMessage() {} } };
vm.createContext(ctx);
vm.runInContext(page.match(/<script>([\s\S]*)<\/script>/)[1], ctx);
// [...x] copies the sandbox's arrays into this realm, so deepStrictEqual can compare them.
const match = q => { const m = ctx.matchCourses(q); return { exact: [...m.exact].map(c => c.name), loose: [...m.loose].map(c => c.name) }; };

// A bare degree abbreviation means its main programme.
assert.deepStrictEqual(match("What is the MCA fee?").exact, ["MCA (Master of Computer Applications)"]);
assert.deepStrictEqual(match("bca fees").exact, ["BCA (Bachelor of Computer Applications)"]);
assert.deepStrictEqual(match("Tell me about BBA").exact, ["BBA (Bachelor of Business Administration)"]);
assert.deepStrictEqual(match("B.Com eligibility").exact, ["B.Com. (Bachelor of Commerce)"]);
assert.deepStrictEqual(match("M.Com last date").exact, ["M.Com (Master of Commerce)"]);
assert.deepStrictEqual(match("MSW admission").exact, ["M.S.W (Master of Social Work)"]);
// Subject words still pick the specialisation.
assert.deepStrictEqual(match("BCA data analytics last date").exact, ["BCA (Data Analytics)"]);
assert.deepStrictEqual(match("msc big data analytics fees").exact, ["M.Sc. Big Data Analytics"]);
// Two degrees, or a subject several programmes share: no single answer, so the student picks.
assert.strictEqual(match("MCA vs BCA").loose.length, 2);
assert.deepStrictEqual(match("msc chemistry").exact, []);
assert.strictEqual(match("msc chemistry").loose.length, 2);
// Not about a programme: no cards.
assert.deepStrictEqual(match("hostel fees"), { exact: [], loose: [] });

console.log("widget matching OK");
