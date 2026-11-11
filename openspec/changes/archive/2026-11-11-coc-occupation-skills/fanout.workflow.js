const root = args.root;
const lanes = [
  { key: "part1", range: "2-20" },
  { key: "part2", range: "21-39" },
  { key: "part3", range: "40-58" },
  { key: "part4", range: "59-77" },
  { key: "part5", range: "78-96" },
  { key: "part6", range: "97-114" },
];

function task(range, key) {
  return `你在 BotEro 仓库（当前工作目录）整理 COC 7 版职业的「本职技能」结构化数据。

只读输入：
- \`${root}/occupations_source.json\`：数组，元素含 seq / name / credit / formula / own_skills（own_skills 是散文）
- \`${root}/canonical_skills.json\`：allowed 技能名 = \`skills\`（39 个规范名）+ \`categories\`（类别前缀）+ \`aliases\`（别名映射）

你负责 **seq = ${range}** 的职业（含两端）。

输出文件：\`${root}/parts/${key}.json\`，内容是一个 JSON 对象，键是 seq 字符串：
\`\`\`json
{ "3": {"required": ["会计", "法律"], "choices": [{"count": 2, "from": "*"}]} }
\`\`\`

拆解规则：
1. 具体技能名 → 放进 \`required\`，必须用规范名（原文「侦查」→「侦察」，「图书馆」→「图书馆使用」，「导航」→「领航」若表里是它）。
2. 「任意 N 项…」「任一…」→ \`{"count": N, "from": "*"}\`。
3. 限定池，如「一项社交技能（魅惑、话术、恐吓、说服）」「两项科学技能（生物学、化学）」→ \`{"count": N, "from": [池内规范名]}\`。
4. 子职业专攻用「类别:专攻」，类别只能来自 \`categories\`，例如 \`技艺:摄影\`、\`科学:生物学\`、\`格斗:剑\`、\`射击:步枪\`、\`语言:拉丁语\`。
5. 去掉句末标点、「。」「、」等噪声；同一技能不要重复。
6. 每个职业 \`len(required) + Σcount\` 必须在 4..8 之间；\`required\` 不得含「克苏鲁神话」「信用评级」。
7. 只写你负责的 seq；不要改动其它文件、不要跑 pytest、不要改代码。输出必须是合法 UTF-8 JSON，无注释、无尾逗号。

完成前自检（必须实际执行）：
用 python 读取 canonical_skills.json 与你的输出，断言每个名字要么在 \`skills\` 里，要么形如 \`类别:专攻\` 且类别在 \`categories\` 里；断言每个职业 slot 总数 4..8。自检不通过就修到通过。

结束时报告：写入的职业数、是否出现需要人工复核的模糊职业（列出职业名与原因）、自检结果。`;
}

const results = await runs.all(
  lanes.map((lane) => ({ key: lane.key, agent: "worker", task: task(lane.range, lane.key) })),
);

for (const item of results) {
  emit(`${item.key}: ${String(item.output || "").slice(0, 400)}`);
}
return results.map((item) => ({ key: item.key, status: item.status }));
