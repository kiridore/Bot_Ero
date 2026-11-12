// COC 资产合计：建卡页与角色卡查看页共用一份口径，避免两处各算一遍而漂移。
// 口径：当前现金 + 其他资产表五类（工具/住所/奢侈品/股票·证券/其他）；
// 含非数字内容（如「5先令」「很多」）时该字段按 0 计，不抛错。
(function () {
  const ITEM_KEYS = ["vehicle", "residence", "luxury", "securities", "other"];

  function toNumber(value) {
    if (typeof value === "number") return Number.isFinite(value) ? value : 0;
    const raw = String(value == null ? "" : value);
    // 维多利亚时代的「5先令」「2镑10先令」这类文本金额无法换算成同一单位，按 0 计
    if (/[一-龥]/.test(raw)) return 0;
    const text = raw.replace(/[^\d.-]/g, "");
    if (!text) return 0;
    const parsed = Number(text);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function total(assets) {
    const source = assets || {};
    return toNumber(source.cash) + ITEM_KEYS.reduce((sum, key) => sum + toNumber(source[key]), 0);
  }

  window.BoteroAssets = { total: total, toNumber: toNumber, ITEM_KEYS: ITEM_KEYS };
})();
