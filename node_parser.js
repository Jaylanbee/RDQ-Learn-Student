const fs = require('fs');
const path = require('path');
const vm = require('vm');
const baseDir = process.argv[2] || process.env.EDS_EXAM_BASE_DIR || "exam-data/questions";
const subjects = ['國文', '數學', '社會', '自然', '英語'];
const years = [111, 112, 113, 114, 115];
const allExams = [];

for (const s of subjects) {
  const dataDir = path.join(baseDir, s, 'data');
  if (!fs.existsSync(dataDir)) continue;

  for (const y of years) {
    const filePath = path.join(dataDir, `q${y}.js`);
    if (!fs.existsSync(filePath)) continue;

    try {
      const code = fs.readFileSync(filePath, 'utf8');
      const context = { window: { BANK: [] } };
      vm.createContext(context);
      vm.runInContext(code, context);

      const item = context.window.BANK[0] || {};
      const questions = item.questions || [];
      const groups = item.groups || {};

      for (const q of questions) {
        let passageText = "";
        let groupTitle = "";
        let groupImg = "";

        if (q.group && groups[q.group]) {
          const g = groups[q.group];
          passageText = g.passage || "";
          groupTitle = g.title || "";
          groupImg = g.image || "";
        }

        allExams.push({
          year: y,
          subject: s,
          no: q.no,
          cat: q.cat || null,
          tags: q.tags || [],
          skill: q.skill || null,
          stem: q.stem || q.officialText || "",
          official_text: q.officialText || "",
          options: q.options || {},
          answer: q.answer || "",
          explain: q.explain || "",
          image: q.image || "",
          group_id: q.group || null,
          passage: passageText,
          group_title: groupTitle,
          group_image: groupImg,
          pass_rate: q.pass !== undefined ? q.pass : null,
          discrim: q.disc !== undefined ? q.disc : null
        });
      }
    } catch (e) {
      console.error(`Error reading ${filePath}:`, e.message);
    }
  }
}
console.log(JSON.stringify(allExams));
