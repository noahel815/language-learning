# language-learning
for JSL learners to generate learning materials

## Japanese Lesson Template V1

- Frozen template: `templates/japanese-lesson-v1.html`
- Template specification: `templates/JAPANESE_TEMPLATE_V1.md`
- Accepted sample lesson: `japanese/JP-V1-001.html`
- Generator data contract: `generator/template-schema.json`
- Next-lesson learning adjustments: `generator/next-lesson-adjustments.json`

To generate a new lesson, prepare lesson data that validates against `generator/template-schema.json`, copy the frozen template to `japanese/<lessonId>.html`, replace every `@@...@@` scalar token, and populate the stable section selectors documented in the template specification. Merge the accepted learning signals from `generator/next-lesson-adjustments.json`, then verify that no tokens remain and test the mobile feedback/clipboard flow. Do not overwrite the accepted `JP-V1-001` sample.

## Japanese Weekly Generator V1

The weekly generator turns one seven-lesson JSON file into seven self-contained lessons, runs static QA, and refreshes the weekly links on `index.html`. It does not call a model, Notion, news services, or GitHub automatically.

For the simplest Windows workflow, double-click `run_weekly_japanese.bat`. See `generator/README.md` for the non-technical instructions, PowerShell command, QA scope, and publishing steps.
