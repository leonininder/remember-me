# 快速上手（繁體中文）

**撰寫：** 2026-09-20（CST / Asia/Taipei）  
**狀態：** PREVIEW — 非正式 skill。Jev 是**決策閘門**，不是聊天模型，**不能產生長文**。

---

## 安裝

```bash
pip install -e ".[dev]"   # Python 3.11+
remember-me demo
remember-me bakeoff
```

預設走離線 **FakeJev**（無網路）。

---

## FakeJev 示範

```python
from remember_me import FakeJev, MemoryPipeline, TopologyGraph

g = TopologyGraph()
g.observe(
    node_id="pref_theme",
    content="User prefers dark theme",
    tags=["preference", "ui"],
    salience=0.9,
)
pipe = MemoryPipeline(g, FakeJev(), top_k=5)
result = pipe.run("What is my UI theme preference?")
assert result.jev_called
for node in result.hydrated:
    print(node.node_id, node.action)
```

**注意：** FakeJev ≠ 線上 TypeSafe。離線 bake-off 數字不可當成雲端延遲或校準品質證據。

---

## HttpJev：System One + query_hash

```python
import os
from remember_me.jev_client import HttpJev

client = HttpJev(
    api_key=os.environ.get("TYPESAFE_API_KEY"),
    # 預設 POST https://api.typesafe.ai/v1/systemone
    include_raw_query=False,  # 只送 query_hash；勿預設外洩原始問句
    batch_candidates=True,    # N 個候選盡量一筆 POST
)
```

- 外送狀態為**已脫敏**的 marker 中繼資料（無正文 / 密鑰）。
- 多候選 hydrate：`state.candidates` + 問題鍵 `{node_id}__hydrate_action` 等。
- 線上模式需真實金鑰與 pilot log；契約已對齊 System One，**尚未**宣稱雲端已驗證。

可選官方 skill：

```bash
npx skills add typesafe-ai/skills --skill typesafe-ai
```

---

## 文件連結

| 文件 | 內容 |
|------|------|
| [COOKBOOK.md](COOKBOOK.md) | Playground、Choice/Score/Noul hydrate 範例、信心門檻表 |
| [MISCONCEPTIONS.md](MISCONCEPTIONS.md) | 常見誤解 |
| [HONEST_LIMITS.md](HONEST_LIMITS.md) | REAL / FAKE / CLAIMED |
| [RUNTIME_HOWTO.md](RUNTIME_HOWTO.md) | FakeJev vs HttpJev |

TypeSafe 文件：[https://docs.typesafe.ai/](https://docs.typesafe.ai/)

---

## YouTube / 社群教學說明

YouTube 影片 [GJJq4LXHtW4](https://www.youtube.com/watch?v=GJJq4LXHtW4) **字幕／逐字稿已停用**，本專案**未**轉錄該影片。我們僅參考公開的**中文社群教學**（例如 wangruofeng007.com 等部落格）作為 System One 方向的**導覽**，不作為官方文件或線上效能證明。
