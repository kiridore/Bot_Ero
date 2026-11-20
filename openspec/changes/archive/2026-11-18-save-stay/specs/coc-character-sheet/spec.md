# coc-character-sheet — 变更（保存后留在编辑页）

## ADDED Requirements

### Requirement: 保存后停留在编辑页
建卡页保存成功（新建或编辑）后 MUST 跳到该卡的编辑页 `/trpg/coc/<id>?saved=1`，MUST NOT 跳回车卡列表；页面加载时若带 `saved=1` MUST 给出「已保存」提示（尚无年龄调整记录时提示「现在可以应用年龄调整」），并在提示后清除该参数。

#### Scenario: 新建卡保存
- **WHEN** 在 `/trpg/coc` 填完信息点保存
- **THEN** 地址变为 `/trpg/coc/<新卡号>?saved=1`，页面提示「已保存，现在可以应用年龄调整」，年龄调整面板可点

#### Scenario: 编辑已有卡
- **WHEN** 在 `/trpg/coc/<id>` 修改后保存
- **THEN** 停留同一页并提示「已保存」

### Requirement: 建卡页具备操作反馈
建卡页 MUST 提供可用的 `showToast`，使补本职技能、按规则填入、年龄调整、撤销等操作的反馈可见。

#### Scenario: 操作反馈
- **WHEN** 点「应用年龄调整」成功
- **THEN** 页面底部出现「年龄调整已应用」提示条，而不是无任何反馈或 ReferenceError
