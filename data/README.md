# Evaluation logs

The six evaluation logs are not part of this repository. They come from two
archives published alongside the tools of Sabine Folz-Weinstein and are
unpacked into `data/benchmark/` (ignored by git):

| Archive | Contents | Size | MD5 |
|---|---|---|---|
| [`Test_POLogs_TokenReplayForPO.zip`](https://raw.githubusercontent.com/sabinefw/TokenBasedReplayForPartialOrders/11bc8fc/Test_POLogs_TokenReplayForPO.zip) | the six **partially ordered** logs, one representative trace per partial-order variant (alpha oracle of the Configurable Concurrency Oracle) | 1 MB | `0a860ba47611b9eaf48f065fe6da1cc1` |
| [`RM_TestDataSeq.zip`](https://raw.githubusercontent.com/sabinefw/ConfigurableConcurrencyOracleTool/38706f9ee1cd20738d1bd7073acbc5e0d5055ce6/RM_TestDataSeq.zip) | the six **sequential source logs** the partial orders were derived from | 6.5 MB (250 MB unpacked) | `98ae5b5fdbaf2b5bbde5538b3392875d` |

The sources are BPI Challenge 2012 and 2019 and Road Traffic Fine Management
(4TU.ResearchData) and `reviewing` and `teleclaims` from the companion material
of van der Aalst, *Process Mining* (2016), chapter 8. The BPI logs are cut-outs
(the `A_`/`O_` activities of BPI 2012, document category C of BPI 2019).

## Unpacking

Both archives keep their files in a top-level folder; unpack them **flat** so the
scripts find the file names they expect:

```bash
cd <repository root>
mkdir -p data/benchmark/po data/benchmark/seq
curl -L -o /tmp/po.zip  https://raw.githubusercontent.com/sabinefw/TokenBasedReplayForPartialOrders/11bc8fc/Test_POLogs_TokenReplayForPO.zip
curl -L -o /tmp/seq.zip https://raw.githubusercontent.com/sabinefw/ConfigurableConcurrencyOracleTool/38706f9ee1cd20738d1bd7073acbc5e0d5055ce6/RM_TestDataSeq.zip
unzip -j /tmp/po.zip  'Test_POLogs_ICPM_TokenReplayForPO/*.xes' -d data/benchmark/po
unzip -j /tmp/seq.zip 'RM_TestData/*.xes'                        -d data/benchmark/seq
```

Afterwards the layout is

```
data/benchmark/po/   BPI12_alog_alpha_logwise_oneRperPoVar.xes
                     BPI12_olog_alpha_logwise_oneRperPoVar.xes
                     bpi2019_C_alpha_logwise_oneRperPoVar.xes
                     reviewing_alpha_logwise_oneRperPoVar.xes
                     roadtrafficfine_alpha_logwise_oneRperPoVar.xes
                     teleclaims_alpha_logwise_oneRperPoVar.xes
data/benchmark/seq/  BPI2012_alog.xes  BPI2012_olog.xes  BPI2019_C.xes
                     reviewing.xes  Road_Traffic_Fine.xes  teleclaims.xes
```

The first archive also contains the token-replay tool itself; only the `.xes`
files under `Test_POLogs_ICPM_TokenReplayForPO/` are needed here.

## Where the scripts look

`scripts/benchmark_logs.py` expects the two folders under `data/benchmark/` of
this repository. To keep the logs elsewhere, set `BENCHMARK_DATA` to a directory
with the same two subfolders `po/` and `seq/`:

```bash
BENCHMARK_DATA=/path/to/logs python scripts/laufzeit_messen.py
```

A script that cannot find a log stops with the missing path and a pointer to
this file.
