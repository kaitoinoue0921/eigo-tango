# サクッと英和（仮称）
広告の少ない英和辞書サイトのプロトタイプ。静的HTML（ビルド不要で配信可）。

## ビルド
1. `tools/data/` に元データを置く（EJDict `ejdict.txt`、Tatoeba `eng.tsv` `jpn.tsv` `links.tsv`、`cmudict.txt`）
2. `python3 tools/fetch_etym.py` … Wiktionaryから語源を取得（中断再開可、約1時間）
3. `BASE_URL=https://独自ドメイン python3 tools/build.py` … `w/` `list/` `sitemap.xml` などを生成

## ライセンス表記（about.html に記載済み）
EJDict=CC0 / Tatoeba=CC BY 2.0 FR / Wiktionary=CC BY-SA 4.0 / CMUdict=BSD系
