# language-learning
for JSL learners to generate learning materials

## Japanese Lesson Template V1

- Frozen template: `templates/japanese-lesson-v1.html`
- Template specification: `templates/JAPANESE_TEMPLATE_V1.md`
- Accepted sample lesson: `japanese/JP-V1-001.html`
- Generator data contract: `generator/template-schema.json`
- Next-lesson learning adjustments: `generator/next-lesson-adjustments.json`

To generate a new lesson, prepare lesson data that validates against `generator/template-schema.json`, copy the frozen template to `japanese/<lessonId>.html`, replace every `@@...@@` scalar token, and populate the stable section selectors documented in the template specification. Merge the accepted learning signals from `generator/next-lesson-adjustments.json`, then verify that no tokens remain and test the mobile feedback/clipboard flow. Do not overwrite the accepted `JP-V1-001` sample.
