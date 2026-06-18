::: titlepage
  -------------------
  Bachelor's Thesis
  -------------------
:::

**Designing an Algorithmic System for Energy Market Forecasting**\
using Machine Learning and MLOps

Bachelor's Thesis\
June 2026

By\
Viet Hoang Nguyen

  --------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------
  Copyright:      Reproduction of this publication in whole or in part must include the customary bibliographic citation, including author attribution, report title, etc.
  Cover photo:    Vibeke Hempler, 2012
  Published by:   DTU, Department of Applied Mathematics and Computer Science, Richard Petersens Plads, Building 324, 2800 Kgs. Lyngby Denmark
                  [www.dtu.dk](www.dtu.dk){.uri}
  --------------- ----------------------------------------------------------------------------------------------------------------------------------------------------------

## Preface {#preface .unnumbered}

This thesis was prepared at DTU Compute, the Department of Applied
Mathematics and Computer Science at the Technical University of Denmark,
in partial fulfilment of the requirements for the degree of Bachelor of
Science in Artificial Intelligence and Data. The work was carried out in
the spring of 2026 under the supervision of Finn Årup Nielsen.

The thesis develops and evaluates an end-to-end system for day-ahead
electricity price forecasting, pairing the benchmark forecasting models
of the literature with the MLOps practices needed to operate them in
production. It assumes the reader is familiar with the basics of machine
learning and applied statistics.

::::: center
:::: minipage
::: center
Viet Hoang Nguyen - s234859

(0.04,0) -- (,0);

*Signature*

(0.04,0) -- (,0);

*Date*
:::
::::
:::::

## Abstract {#abstract .unnumbered}

Research on day-ahead electricity price forecasting (EPF) has produced
accurate benchmark models but evaluates them only offline, away from the
concerns that arise once a model runs in production, such as scheduled
retraining, monitoring, and reproducibility. This thesis addresses that
gap by embedding the benchmark EPF models of Lago et al., the LEAR
ensemble and a deep neural network, together with the Transformer of
Llorente and Portela, in an end-to-end MLOps platform, and by evaluating
both the forecasts and the system. The platform ingests ENTSO-E data on
a schedule, stores it in ClickHouse, recalibrates and forecasts daily
for the DK1 and DE bidding zones, monitors data and model health, and
records the provenance of every run. The three models are replicated to
specification and compared on a shared recent test window with paired
Giacomini--White significance tests. LEAR and a tuned DNN are
statistically tied as the most accurate models on both markets
($p>0.16$), both significantly outperform the pure Transformer
($p\le0.013$), and all three beat the weekly-naive baseline. The source
papers' model rankings do not replicate under the reduced tuning budget
used here. The system is assessed against the nine MLOps practices of
Zarour et al. Eight are realised end-to-end and one is minimally
realised. Building the platform around the benchmark models surfaced
engineering trade-offs that largely aligned the needs of a faithful
replication with those of a single-host production system. The
assessment is supported by an ML Test Score of 2.5 bound by data
testing, and provenance coverage of 100 % from the first
continuously-deployed run, 66.7 % across the full window, backed by a
re-run that reproduced a logged forecast to within
$7\times10^{-6}$ EUR/MWh. The result is a reproducible, monitored EPF
platform and a faithful, significance-tested model comparison on current
market data.

## Acknowledgements {#acknowledgements .unnumbered}

I would like to thank my supervisor, Finn Årup Nielsen, for his guidance
and support throughout this project.

## Use of Artificial Intelligence {#use-of-artificial-intelligence .unnumbered}

Artificial-intelligence tools, principally Anthropic's Claude Code, were
used throughout this project as an enhancement to the author's own work
and not a replacement for it. They supported two activities, namely
building the code base behind the platform and reformulating and
reviewing the content of this report. The author directed the work in
every case, read and understood every line of generated code before
committing it, and confirmed and reviewed every design decision, never
adopting a suggestion unchecked. The author is fully responsible for the
final code, the design choices, and the text of this report.

The collaboration is recorded so that it can be inspected. Each commit
made together with Claude carries a co-authorship trailer in the
project's Git history, so the tool's involvement in any individual
change is traceable. The plans and design notes that Claude produced
during the work are kept in the repository's `docs` folder, where they
are located next to the code and documents. The repository is available
at <https://github.com/vietnhprivat/algo-repo-public>.

## Acronyms {#acronyms .unnumbered}

CI/CD

:   Continuous Integration / Continuous Delivery

CRPS

:   Continuous Ranked Probability Score

DNN

:   Deep Neural Network

ENTSO-E

:   European Network of Transmission System Operators for Electricity

EPF

:   Electricity Price Forecasting

GW

:   Giacomini--White (test of conditional predictive ability)

LEAR

:   Lasso Estimated AutoRegressive (model)

MAE

:   Mean Absolute Error

MIMO

:   Multiple-Input Multiple-Output

MLOps

:   Machine Learning Operations

MVP

:   Minimum Viable Product

rMAE

:   relative Mean Absolute Error

RMSE

:   Root Mean Squared Error

sMAPE

:   symmetric Mean Absolute Percentage Error

TPE

:   Tree-structured Parzen Estimator

# Introduction {#ch:introduction}

## Motivation

Day-ahead electricity price forecasting (EPF) is the task of predicting
the wholesale price of electricity for each delivery period of the
following day in a given bidding zone, from a combination of historical
prices and exogenous signals such as load and renewable-generation
forecasts. Accurate day-ahead forecasts are essential to generators,
retailers, and grid operators, who rely on them to schedule production,
hedge positions, and bid into the day-ahead auction. The task has grown
harder over the past decade. The expansion of wind and solar generation
introduces supply-side volatility that statistical models struggle to
capture, and the coupling of European bidding zones introduces price
shocks across borders in ways historical data may not reflect. The
resulting price series are heavy-tailed and spike-prone. High renewable
output can push prices below zero. Negative prices are incompatible with
transformations that require positive input, so a log transform is not
applicable here. [@weron2014].

## The gap between forecasting research and operation

Research on EPF has produced increasingly accurate models, spanning
statistical, reduced-form, and machine-learning approaches, and the
field has been studied in depth [@weron2014; @nowotarski2018]. The
open-access benchmark of Lago et al. [@lago2021] was an important step,
documenting how severe the evaluation problem had become. New methods
were compared on private datasets, over test periods too short to be
conclusive, and against baselines too weak to be informative. In
response, Lago et al. standardised both a pair of benchmark models and a
methodology for comparing them.

Yet even the most careful EPF contributions stop at the boundary of
offline evaluation. They standardise how models are compared, but not
how they are run. Ingesting data on a schedule, versioning experiments,
detecting model degradation, and retraining on fresh data are left
unaddressed. This gap between building a model and operating it is the
one that Machine Learning Operations (MLOps) emerged to close, by
carrying DevOps principles such as automation, reproducibility, and
monitoring into machine-learning systems. In Zarour et al. [@zarour2025]
the MLOps literature is presented as a systematic review of nine core
practices and a maturity model. The two fields of work rarely meet. EPF
research treats forecasting as a problem that ends when predictions are
produced, while MLOps research is largely domain focused. The closest
precedent for joining them is the work of Subramanya et
al. [@subramanya2022devops2mlops], who apply an MLOps pipeline to
electricity-market forecasting as a case study.

## Aim and research questions

This thesis takes the benchmark EPF models from the forecasting
literature and embeds them in a production platform built along MLOps
principles. The platform ingests data from the ENTSO-E Transparency
Platform on a recurring schedule, stores it in ClickHouse, produces
day-ahead forecasts through rolling-window recalibration, monitors
prediction quality and data drift, and maintains a complete audit trail
from every forecast back to the code version and data window that
produced it. It is evaluated on two axes, the forecast quality of the
models it serves and the operational maturity of the system that serves
them. Three research questions structure the investigation.

RQ1 (forecasting).

:   How do replicated LEAR, DNN, and Transformer day-ahead EPF models
    compare on recent ENTSO-E data for the DK1 and DE bidding zones,
    when set against one another, a weekly-naive baseline, and the
    rankings reported by Lago et al. [@lago2021] and Llorente and
    Portela [@llorente2025transformer]?

RQ2 (engineering).

:   What engineering trade-offs and operational constraints emerge when
    implementing these benchmark models into a scheduled, containerised,
    continuously monitored production pipeline?

RQ3 (maturity).

:   Assessed against the nine MLOps practices of Zarour et
    al. [@zarour2025] and the Google maturity model, which practices
    does the platform realise, which prove most critical, and where does
    a single-host minimum-viable platform (MVP) reach its limit?

## Contributions

This work makes four contributions.

- **A production EPF platform.** A system that ingests live ENTSO-E
  data, recalibrates and forecasts on a daily schedule, monitors data
  and model health, and records the full provenance of every run. This
  is what the RQ2 and RQ3 are evaluated against.

- **A faithful model replication.** LEAR and the DNN of Lago et
  al. [@lago2021] and the Transformer of Llorente and Portela
  [@llorente2025transformer], reimplemented to specification and
  compared across two markets on a shared recent test window with paired
  Giacomini--White significance tests (RQ1).

- **A composed quantitative MLOps evaluation.** A combination of the ML
  Test Score rubric, provenance-coverage measurement, and a
  reproducibility re-run, to compliment the other qualitative maturity
  question with a quantitative metric.

- **A practice-by-practice maturity assessment** of the platform against
  Zarour et al.'s nine practices, with each practice traced to a
  concrete repository artefact and positioned on the Google maturity
  model.

The scope is bounded. The work only forecasts spot prices, and not
probabilistic distributions. It is a single-case study of one platform,
so its system-side findings support analytic rather than statistical
generalisation. Because the source papers' test periods predate the
present price regime, the forecasting comparison is framed in relative
terms (rMAE and rankings) and not as a comparison of absolute errors.

## Report structure

Chapter [3](#ch:background){reference-type="ref"
reference="ch:background"} reviews the EPF and MLOps literatures and the
evaluation methodology this work draws on.
Chapter [4](#ch:methods-models){reference-type="ref"
reference="ch:methods-models"} specifies the three forecasting models,
their features, the recalibration scheme, and the metrics and
significance tests used to compare them.
Chapter [5](#ch:system-implementation){reference-type="ref"
reference="ch:system-implementation"} documents the production system
around those models, organised around Zarour's nine practices.
Chapter [6](#ch:results-models){reference-type="ref"
reference="ch:results-models"} reports the forecasting comparison, and
Chapter [7](#ch:results-system){reference-type="ref"
reference="ch:results-system"} sets out how the system is evaluated and
reports the result. Chapter [8](#ch:discussion){reference-type="ref"
reference="ch:discussion"} answers the three research questions and
draws the two threads together, and
Chapter [9](#ch:conclusion){reference-type="ref"
reference="ch:conclusion"} concludes and identifies future work.

# Background and Related Work {#ch:background}

This chapter reviews the two literatures the thesis joins, electricity
price forecasting and MLOps, together with the evaluation methodology it
borrows from empirical software engineering.
Section [3.1](#sec:bg-epf){reference-type="ref" reference="sec:bg-epf"}
covers day-ahead EPF. Section [3.2](#sec:bg-lago){reference-type="ref"
reference="sec:bg-lago"} introduces the open-access benchmark that
anchors the modelling.
Section [3.3](#sec:bg-transformer){reference-type="ref"
reference="sec:bg-transformer"} describes the Transformer approach that
is used by the third model.
Section [3.4](#sec:bg-mlops){reference-type="ref"
reference="sec:bg-mlops"} introduces the MLOps practices and maturity
models behind the system.
Section [3.5](#sec:bg-eval){reference-type="ref"
reference="sec:bg-eval"} lists the instruments used to evaluate the
platform.

## Day-ahead electricity price forecasting {#sec:bg-epf}

In a day-ahead market, participants submit bids for each delivery period
of the following day and a uniform clearing price is set, once per day,
at the intersection of aggregated supply and demand within each bidding
zone. The clearing price is set by the marginal generator, so it
inherits the cost structure of the generation mix and the topology of
cross-border exchange. This mechanism produces a price series with
different seasonalities (daily, weekly, and annual), heavy tails, and
sudden spikes driven by scarcity or congestion. As wind and solar
capacity has grown, sharp drops and negative prices have become more
frequent. Weron's review [@weron2014] surveys the statistical and
computational-intelligence methods developed for this problem, and
Nowotarski and Weron [@nowotarski2018] extend the picture to
probabilistic forecasting. Both emphasise that the EPF methodology, and
not only the choice of model, determines whether reported gains are
real.

## The Lago et al. open-access benchmark {#sec:bg-lago}

Lago et al. [@lago2021] address the reproducibility problem in EPF
directly, contributing an open-access benchmark comprising five market
datasets (Nord Pool, PJM, and the EPEX zones BE, FR, and DE), two
reference models, and the `epftoolbox` library that standardises data
splits and evaluation. The first reference model, LEAR (Lasso Estimated
AutoRegressive), fits an $L^1$-regularised linear model over a
parameter-rich feature space of price lags, exogenous forecasts, and
calendar dummies. The Lasso does feature selection and coefficient
estimation at once, shrinking many coefficients to zero so the large set
of inputs stays manageable. The second is a deep neural network, a
multi-layer perceptron whose architecture and inputs are tuned per
dataset. Despite its simplicity, LEAR matched or outperformed the deep
alternative when evaluated over long test periods, which is why it
serves as the modelling foundation of this thesis.

Two methodological contributions of the benchmark are reused here
directly. First, models are recalibrated on a rolling window and their
forecasts averaged across an ensemble of window lengths, rather than
trained once. Second, the benchmark argues for the relative mean
absolute error (rMAE), which normalises the model's error by that of a
naive baseline so that results remain comparable across periods and
markets, and for formal significance testing of accuracy differences via
the Diebold--Mariano [@diebold1995dm] and multivariate Giacomini--White
[@giacomini2006gw] tests. The benchmark also adopts the
inverse-hyperbolic-sine (asinh) variance-stabilising transform of
Uniejewski et al. [@uniejewski2018vst], which compresses spikes while
remaining defined for negative prices.

## Transformer approaches to EPF {#sec:bg-transformer}

Attention-based architectures have more recently been applied to EPF.
Llorente and Portela [@llorente2025transformer] propose an encoder-only
Transformer. It takes two inputs, a sequence of the previous days'
prices and the day-ahead exogenous forecasts. It embeds and attends over
the price sequence, then combines the result with the exogenous
representation through a final multi-layer perceptron. Benchmarked on
the same open-access datasets, it provides the third model family
compared in this work. The authors evaluate without retraining inside
the test period, applying only a renormalisation step between days. This
thesis instead places the Transformer in the same rolling-recalibration
pipeline as the other models, a deviation documented in
Chapter [4](#ch:methods-models){reference-type="ref"
reference="ch:methods-models"}.

## MLOps practices and maturity {#sec:bg-mlops}

MLOps applies DevOps principles such as automation, version control,
continuous delivery, and monitoring to the particular demands of
machine-learning systems, where data and models, not only code, evolve
over time. Zarour et al. [@zarour2025] consolidate the field in a
systematic literature review that identifies nine recurring best
practices. These are automating CI/CD, orchestrating workflows, ensuring
reproducibility, versioning, collaboration and communication,
continuously training and evaluating models, tracking and logging ML
metadata, continuous monitoring, and implementing feedback loops. These
nine practices provide the structure for the system chapter
(Chapter [5](#ch:system-implementation){reference-type="ref"
reference="ch:system-implementation"}).

The same review has five MLOps maturity models, all descended from the
CMM/CMMI lineage. These are the Google three level model, the Microsoft
and GigaOm five level models, a four level model of John, Olsson and
Bosch, and the five level model of Mateo-Casalí et al. This work
positions the platform against the Google model
[@google_mlops_maturity], which three levels (manual process,
ML-pipeline automation, and CI/CD-pipeline automation) match the
granularity of a single-host platform. That choice is justified in
Chapter [7](#ch:results-system){reference-type="ref"
reference="ch:results-system"}. The closest domain application is
Subramanya et al. [@subramanya2022devops2mlops], who build an MLOps
pipeline for an electricity-market forecasting task and evaluate it as a
case study. This is the precedent this thesis follows in evaluating its
own platform in its real operating context.

## Evaluating machine-learning systems {#sec:bg-eval}

Because the platform is a single artefact rather than a sample, its
system-side evaluation follows the single-case study methodology of
Runeson and Höst [@runeson2009casestudy]. That method supports analytic
generalisation, extending findings to cases that share the platform's
characteristics, rather than statistical generalisation to a population.
Within that frame, several established methods are used. The ML Test
Score of Breck et al. [@breck2017mltestscore] is a 28-item rubric across
four sections (data, model development, ML infrastructure, and
monitoring) whose final score is the minimum of the four section sums,
so the weakest area bounds the result. Reproducibility is reported in
two senses, provenance coverage across runs and a worked re-run of one,
following Gundersen and Kjensmo [@gundersen2018reproducibility]. The
decision of whether drift should trigger retraining is informed by the
cost-aware analysis of Mahadevan and Mathioudakis
[@mahadevan2024costaware], who show that triggered retraining is
worthwhile mainly when retraining is expensive. How these instruments
are applied, and why each was chosen, is evaluated in
Chapter [7](#ch:results-system){reference-type="ref"
reference="ch:results-system"}.

# Forecasting Models and Evaluation {#ch:methods-models}

This chapter specifies the forecasting models that the platform serves
and the protocol by which they are compared. Three model are studied,
the Lasso Estimated AutoRegressive ensemble (LEAR) and the deep neural
network (DNN) of Lago et al. [@lago2021], and the encoder-only
Transformer of Llorente and Portela [@llorente2025transformer]. Each is
reimplemented faithfully and run on recent day-ahead data for two
European bidding zones, DK1 (Nord Pool) and DE (EPEX). The chapter first
states what \"faithful replication\" means and why the comparison is
framed in relative rather than absolute terms
(§[4.1](#sec:mm-framing){reference-type="ref"
reference="sec:mm-framing"}), then describes the data and feature
construction (§[4.2](#sec:mm-data){reference-type="ref"
reference="sec:mm-data"}), the three models as implemented
(§[4.3](#sec:mm-models){reference-type="ref"
reference="sec:mm-models"}), the rolling recalibration and backtesting
method (§[4.4](#sec:mm-recalibration){reference-type="ref"
reference="sec:mm-recalibration"}), the evaluation metrics and
significance tests (§[4.5](#sec:mm-eval){reference-type="ref"
reference="sec:mm-eval"}), the hyperparameter-tuning
(§[4.6](#sec:mm-tuning){reference-type="ref"
reference="sec:mm-tuning"}), and the documented deviations from the
source papers (§[4.7](#sec:mm-deviations){reference-type="ref"
reference="sec:mm-deviations"}).

## Replication framing {#sec:mm-framing}

The results reported in the source papers were obtained on 2016--2018
test periods whose price level and volatility differ from the current
2025--2026 regime. An absolute mean-error figure is therefore not
comparable across the two eras. The comparison this work makes has three
parts. The methodology is replicated first, reusing the same model
specifications, feature sets, recalibration scheme, metrics, and
statistical tests as the papers on current data. Relative accuracy is
then measured through the relative mean absolute error (rMAE) that Lago
et al. [@lago2021] designed for cross-period and cross-market
comparison, alongside the ordinal ranking of the models against the
rankings the papers report. Head-to-head significance is tested last,
with paired Giacomini--White [@giacomini2006gw] tests across the three
models and a weekly-naive baseline, per market, on identical test days.
Because all six experimental runs, three models across two markets,
share a single test window, the paired tests are valid, since every pair
of models is compared on the same delivery days.

## Data and features {#sec:mm-data}

::: tabularx
\@l l l \>

X@

**Market** & **Resolution** & **Exogenous (paper-exact)** & **Paper
analogue**\
DK1 & hourly (24)^a^ & TotalLoad + Wind (on+offshore) & Nord Pool load +
wind [@lago2021]\
DE & hourly (24)^a^ & TotalLoad + Renewables (wind+solar) & EPEX-DE
load + wind&solar [@lago2021]\
\
\
:::

All data are obtained from the ENTSO-E Transparency Platform and stored
in ClickHouse, from which the preprocessor loads a price series and a
configurable set of exogenous forecast series for each market. The data
arrive in long, time series form, one row per delivery period (an hour,
or a quarter-hour before downsampling) the preprocessor pivots each
series to the daily-wide layout of
Fig. [4.1](#fig:mm-pivot){reference-type="ref"
reference="fig:mm-pivot"}, from which the per-day feature vector is
created.

<figure id="fig:mm-pivot" data-latex-placement="h">
<span class="image placeholder" data-original-image-src="f-pivot-wide"
data-original-image-title="" width="92%"></span>
<figcaption>Reshaping from the stored long (time-series) form, one row
per hour, to the daily-wide layout the models consume, one row per day
with the <span class="math inline"><em>n</em> = 24</span> hourly prices
as columns (<span
class="math inline"><em>h</em><sub>1</sub>, …, <em>h</em><sub>24</sub></span>).
Lagged price and exogenous blocks are built by joining date-shifted
copies of these wide rows.</figcaption>
</figure>

Following Lago et al. [@lago2021], Eq. 3, the per-day feature vector
combines autoregressive price lags, lagged exogenous forecasts, and
seven day-of-week dummies. For a day discretised into $n$ delivery
periods this creates $$\begin{equation}
  \underbrace{4n}_{\text{price lags}} + \underbrace{2 \cdot 3n}_{\text{two exogenous} \times \text{3 lags}} + \underbrace{7}_{\text{weekday}}
  \label{eq:mm-featurecount}
\end{equation}$$ features, i.e. $247$ at hourly resolution ($n{=}24$)
and $967$ at quarter-hourly resolution ($n{=}96$).

The target undergoes the asinh variance-stabilising transform of
Uniejewski et al. [@uniejewski2018vst], which compresses the heavy tails
and price spikes characteristic of day-ahead series while, unlike a
logarithm, remaining defined for the negative prices that occur under
high renewable generation. Prices and exogenous forecasts are
downsampled to an hourly mean before features are constructed
(Table [\[tab:mm-datasets\]](#tab:mm-datasets){reference-type="ref"
reference="tab:mm-datasets"}), which keeps the two markets comparable
with each other and with the hourly reference benchmarks of Lago et
al. [@lago2021] and Llorente and Portela [@llorente2025transformer];
modelling DK1 natively at 96 periods is in any case infeasible, with
under one month of quarter-hourly history before the test window.

## Models {#sec:mm-models}

Table [4.1](#tab:mm-models){reference-type="ref"
reference="tab:mm-models"} summarises the three model setups, which are
identical across both markets except for the per-market DNN
hyperparameters.

::: {#tab:mm-models}
  **Model**     **Specification**                                                                                                **Calibration**                  **Refit**
  ------------- ---------------------------------------------------------------------------------------------------------------- -------------------------------- -----------
  LEAR          One Lasso per delivery period, $\lambda$ by `LassoCV` (time-series CV)                                           ensemble over 56 / 84 / 1092 d   daily
  DNN           MLP, architecture HPs by Optuna TPE (ex-ante validation), 4-seed ensemble at serving (single seed in backtest)    d                               daily
  Transformer   Encoder stack per [@llorente2025transformer], paper Nord Pool hyperparameters                                     d                               weekly

  : Model setups (one row per model, identical across both markets
  unless noted).
:::

### LEAR

LEAR is a direct multi-period regressor. One independent Lasso model is
fitted per delivery period, so an hourly market trains $n{=}24$ separate
estimators, each predicting a single period from the full feature vector
of
Eq. [\[eq:mm-featurecount\]](#eq:mm-featurecount){reference-type="eqref"
reference="eq:mm-featurecount"}. Writing $x^1,x^2$ for the two exogenous
series and $z_d$ for the seven day-of-week dummies, the
(asinh-transformed) price for period $h$ is modelled, following Lago et
al. [@lago2021], Eq. 3, as a linear combination of the price lags, the
exogenous lags, and the weekday dummies, $$\begin{equation}
\begin{aligned}
  \hat{p}_{d,h} = {}
   & \sum_{i=1}^{n}\theta_{h,i}\,p_{d-1,i}
   + \sum_{i=1}^{n}\theta_{h,n+i}\,p_{d-2,i}
   + \sum_{i=1}^{n}\theta_{h,2n+i}\,p_{d-3,i}
   + \sum_{i=1}^{n}\theta_{h,3n+i}\,p_{d-7,i} \\[2pt]
   & + \sum_{i=1}^{n}\theta_{h,4n+i}\,x^{1}_{d,i}
   + \sum_{i=1}^{n}\theta_{h,5n+i}\,x^{2}_{d,i}
   + \sum_{i=1}^{n}\theta_{h,6n+i}\,x^{1}_{d-1,i}
   + \sum_{i=1}^{n}\theta_{h,7n+i}\,x^{2}_{d-1,i} \\[2pt]
   & + \sum_{i=1}^{n}\theta_{h,8n+i}\,x^{1}_{d-7,i}
   + \sum_{i=1}^{n}\theta_{h,9n+i}\,x^{2}_{d-7,i}
   + \sum_{j=1}^{7}\theta_{h,10n+j}\,z_{d,j},
\end{aligned}
\label{eq:mm-lear}
\end{equation}$$ where $\boldsymbol{\theta}_h\in\mathbb{R}^{10n+7}$
($=\mathbb{R}^{247}$ at $n{=}24$) collects the coefficients for period
$h$. They are estimated by least squares under an $L^1$ penalty (the
LASSO of [@lago2021], Eq. 4), $$\begin{equation}
  \hat{\boldsymbol{\theta}}_h
   = \arg\min_{\boldsymbol{\theta}_h}\
     \sum_{d}\bigl(p_{d,h}-\hat{p}_{d,h}\bigr)^2
     + \lambda\,\lVert\boldsymbol{\theta}_h\rVert_1,
   \qquad
   \lVert\boldsymbol{\theta}_h\rVert_1=\sum_{k=1}^{10n+7}\lvert\theta_{h,k}\rvert ,
\label{eq:mm-lasso}
\end{equation}$$ so the penalty performs simultaneous shrinkage and
feature selection and keeps the parameter-rich input space manageable.
The strength $\lambda\ge0$ is selected automatically per period by
`LassoCV` with a five-fold `TimeSeriesSplit` cross-validation (maximum
5000 coordinate-descent iterations), the configuration denoted
`alpha="auto"`. LEAR carries no learned ensembling of its own; the
ensemble averaging it benefits from is supplied by the multi-window
recalibration scheme of
§[4.4](#sec:mm-recalibration){reference-type="ref"
reference="sec:mm-recalibration"}.

### Deep neural network

The DNN is a multi-layer perceptron with two hidden layers that maps the
feature vector of
Eq. [\[eq:mm-featurecount\]](#eq:mm-featurecount){reference-type="eqref"
reference="eq:mm-featurecount"} to all $n$ delivery periods in a single
forward pass, a multiple-input multiple-output (MIMO) design
(Fig. [4.2](#fig:mm-dnn){reference-type="ref" reference="fig:mm-dnn"}).

<figure id="fig:mm-dnn" data-latex-placement="H">
<span class="image placeholder"
data-original-image-src="f-dnn-architecture"
data-original-image-title="" width="82%"></span>
<figcaption>The DNN, after Lago et al. <span class="citation"
data-cites="lago2021"></span>, Fig. 4, a fully-connected multi-layer
perceptron from the feature vector of Eq. <a href="#eq:mm-featurecount"
data-reference-type="eqref"
data-reference="eq:mm-featurecount">[eq:mm-featurecount]</a> to the
<span class="math inline"><em>n</em></span> delivery periods. The two
hidden layers share a single tuned width (Table <a href="#tab:mm-dnn-hp"
data-reference-type="ref" data-reference="tab:mm-dnn-hp">4.2</a>, 191
for DK1 and 373 for DE); the number of units drawn is
schematic.</figcaption>
</figure>

It is trained to minimise the mean absolute error with the Adam
optimiser, with optional $L^1$ weight regularisation, optional batch
normalisation, and early stopping. The prediction is the mean of four
replicates trained from distinct random seeds, following Lago et
al. [@lago2021], §4.4; this four seed averaging is applied only on the
production serving path. The rolling backtest behind the
Chapter [6](#ch:results-models){reference-type="ref"
reference="ch:results-models"} results trains a single network per
recalibration at a fixed seed, so the reported DNN metrics carry the
seed variance of one draw. The six architecture hyperparameters
(hidden-layer width, activation, dropout, learning rate, the
batch-normalisation flag, and the $L^1$ penalty) are selected per market
by the tuning protocol of §[4.6](#sec:mm-tuning){reference-type="ref"
reference="sec:mm-tuning"};
Table [4.2](#tab:mm-dnn-hp){reference-type="ref"
reference="tab:mm-dnn-hp"} lists the values in force.

::: {#tab:mm-dnn-hp}
  **Market**   **Width**   **Activation**   **Dropout**   **Learning rate**    **Batch norm**   **$L^1$ penalty**
  ------------ ----------- ---------------- ------------- -------------------- ---------------- --------------------
  DK1          191         tanh             0.203         $4.8\times10^{-4}$   no               $6.8\times10^{-8}$
  DE           373         relu             0.204         $6.9\times10^{-4}$   yes              $7.1\times10^{-7}$

  : Tuned DNN hyperparameters per market. Selected by the protocol of
  §[4.6](#sec:mm-tuning){reference-type="ref" reference="sec:mm-tuning"}
  on the validation window. The search is re-run whenever the feature
  set changes, so these values are refreshed by the paper exogenous
  re-tune that accompanies the final benchmark.
:::

### Transformer

The Transformer follows Llorente and Portela [@llorente2025transformer]
and is encoder-only with two parallel input branches
(Fig. [4.3](#fig:mm-transformer){reference-type="ref"
reference="fig:mm-transformer"}).

<figure id="fig:mm-transformer" data-latex-placement="h">
<span class="image placeholder"
data-original-image-src="f-transformer-flow"
data-original-image-title="" width="60%"></span>
<figcaption>The encoder-only Transformer, after Llorente and
Portela <span class="citation"
data-cites="llorente2025transformer"></span>, Fig. 2a. The past-price
sequence is embedded and given a learnable positional encoding before
the encoder stack; the day-ahead exogenous forecasts are embedded in
parallel; the two representations are concatenated and mapped to the
<span class="math inline"><em>n</em></span> output periods by an
MLP.</figcaption>
</figure>

The price branch takes the previous $m{=}14$ days, each a vector of $n$
period prices, each day is linearly embedded to 128 dimensions, a
learnable positional encoding is added, and the sequence passes through
six encoder layers (eight attention heads, feed-forward dimension 1024,
dropout 0.2), the final position giving the price representation. The
exogenous branch linearly embeds the day-ahead forecasts. The
concatenated representations are mapped by a single-hidden-layer
perceptron (width 128) to the $n$ output periods. Training uses Adam at
learning rate $10^{-4}$, batch size 32, up to 200 epochs with early
stopping on an internal validation split, under a step learning-rate
schedule. The number of exogenous inputs is fixed at two to match the
paper, and the remaining hyperparameters follow the paper's reported
architecture and search ranges rather than a per-market optimum. The
128-dimensional embedding lies within the paper's range but below its
Nord Pool optimum of 512, and per-market tuning is left as future work
(§[4.7](#sec:mm-deviations){reference-type="ref"
reference="sec:mm-deviations"}).

## Recalibration and backtesting {#sec:mm-recalibration}

All three models are evaluated by a single forward backtesting engine
that reproduces the rolling recalibration scheme of Lago et
al. [@lago2021], illustrated in
Fig. [4.4](#fig:mm-recalibration){reference-type="ref"
reference="fig:mm-recalibration"}. For each delivery day in the test
window, and for each calibration window length in the model's ensemble,
the engine slices the training data to the most recent window of days
strictly preceding the target day, fits the feature and target scalers
on that slice alone, trains the model, and predicts the target day. The
forecast is then the mean of the predictions across the windows.

<figure id="fig:mm-recalibration" data-latex-placement="h">
<span class="image placeholder"
data-original-image-src="f-recalibration" data-original-image-title=""
width="\linewidth"></span>
<figcaption>Rolling walk forward recalibration with a calibration window
ensemble, after Lago et al. <span class="citation"
data-cites="lago2021"></span>. For each test day the data are sliced to
the most recent window of each ensemble length (shown for LEAR,
56/84/1092 days), every window is refit and predicts the target day, and
the forecast is their average. The boundary then advances one day;
models refit daily (LEAR, DNN) or weekly (Transformer).</figcaption>
</figure>

To bound compute, each window keeps a cached fitted model and is
refitted only when the days since its last fit reach the configured
refit interval, daily for LEAR and the DNN and weekly for the
Transformer, following the respective papers. LEAR uses the paper
ensemble of 56, 84, and 1092 day windows; the 1456 day window of the
original specification is dropped because it predates the available
data. The DNN uses a single 730 day window, and the Transformer a single
1092 day window, verified to leave enough usable sequence rows before
the test start in both markets.

## Evaluation protocol {#sec:mm-eval}

The test window runs from 2025-10-24 to 2026-05-31 (220 calendar days)
and is identical for all six runs. Four accuracy metrics are reported.
For $N$ aligned prediction--actual pairs $(\hat{y}_i, y_i)$,
$$\begin{align}
  \mathrm{MAE}   &= \frac{1}{N}\sum_{i=1}^{N} \lvert y_i - \hat{y}_i \rvert,
  & \mathrm{RMSE} &= \sqrt{\frac{1}{N}\sum_{i=1}^{N} (y_i - \hat{y}_i)^2}, \\
  \mathrm{sMAPE} &= \frac{100}{N}\sum_{i=1}^{N} \frac{\lvert y_i - \hat{y}_i\rvert}{\tfrac{1}{2}(\lvert y_i\rvert + \lvert \hat{y}_i\rvert)},
  & \mathrm{rMAE} &= \frac{\mathrm{MAE}(\mathbf{y}, \hat{\mathbf{y}})}{\mathrm{MAE}(\mathbf{y}, \hat{\mathbf{y}}^{\text{naive}})},
\end{align}$$ where the naive benchmark
$\hat{\mathbf{y}}^{\text{naive}}$ is the weekly-naive forecast (the
realised price exactly seven days earlier), as recommended by Lago et
al. [@lago2021], §5.4. The rMAE is the headline metric because, being
normalised by the same-market naive error, it is the figure that can be
compared across periods and markets.

Statistical significance is assessed with the multivariate
Giacomini--White test [@giacomini2006gw; @lago2021]. For each ordered
pair of models $(A,B)$ the daily loss differential $$\begin{equation}
  d_t = \sum_{h=1}^{n} \bigl(\lvert e^{A}_{t,h}\rvert - \lvert e^{B}_{t,h}\rvert\bigr)
\end{equation}$$ is formed over the $n$ delivery periods of day $t$ (the
$L^1$ norm of the errors), and the test statistic
$\bar{d}/\hat{\sigma}_{\bar d}$ is computed with a Newey--West
heteroskedasticity- and autocorrelation-consistent standard error using
a lag of $\lfloor T^{1/4}\rfloor$ over the $T$ test days. Models are
compared on the test days that all of them produced, since the different
feature pipelines drop gap and daylight-saving days slightly differently
across model families. Finally, computation cost is reported as the
training time per recalibration, read from the experiment tracker, as
the analogue of Lago et al. [@lago2021], Table 4.

## Hyperparameter tuning {#sec:mm-tuning}

Only the DNN is tuned; LEAR cross-validates $\lambda$ internally and the
Transformer reuses the paper optimum
(Table [4.1](#tab:mm-models){reference-type="ref"
reference="tab:mm-models"}). Its six architecture hyperparameters are
searched with Optuna's Tree-structured Parzen Estimator over
hidden-layer width ($16$--$512$, log), activation (relu, tanh, elu,
softplus, or sigmoid), dropout ($0$--$0.5$), learning rate
($10^{-5}$--$10^{-1}$, log), the batch-normalisation flag, and the $L^1$
penalty ($10^{-8}$--$10^{-2}$, log). The objective is the mean MAE over
a validation window (2025-01-01 to 2025-10-23, the 42 weeks before the
test window; [@lago2021], §4.3.2), scored under the same walk-forward
engine as the backtest, with each trial persisted to
`algo.hyperparam_trials` for resumable search. Lago's ten binary
feature- and selector-toggles, and their `preprocessing` and
`init_method` choices, are omitted. The preprocessor exposes no such
switches, so they would only add inert search dimensions
(Table [4.3](#tab:mm-deviations){reference-type="ref"
reference="tab:mm-deviations"}).

## Deviations from the source papers {#sec:mm-deviations}

The replication is faithful in specification but departs from the source
papers in a small number of things, summarised in
Table [4.3](#tab:mm-deviations){reference-type="ref"
reference="tab:mm-deviations"}. Each deviation is driven either by the
length of the available data history or by a compute budget, and none
changes the model class or the feature definition.

::: {#tab:mm-deviations}
  **Aspect**             **Paper**                                 **This work (reason)**
  ---------------------- ----------------------------------------- -------------------------------------------------------------------------------------------------------
  Test length            $\geq$ 1--2 years                         weeks (price history starts 2022-03, and validation and calibration consume the rest)
  DNN tuning budget      TPE iterations                            trials (compute budget, architecture-only search space)
  DNN search space       architecture + feature selectors          architecture only (feature set fixed to the paper specification)
  LEAR windows           / 84 / 1092 / 1456 d                      / 84 / 1092 d (1456 predates the data)
  DNN window             years                                      d (data and compute constraint)
  $\lambda$ selection    LARS+AIC, then coordinate-descent refit   `LassoCV` time-series CV (standard, close accuracy)
  Market resolution      hourly (paper era)                        both markets now 15-min, downsampled to an hourly mean for cross-market and cross-paper comparability
  Transformer pipeline   train-once + renormalise                  calibration window + weekly refit (consistency with the other models)
  Transformer HPs        tuned per dataset                         paper architecture / search-range defaults reused (per-market tuning is future work)

  : Documented deviations from [@lago2021]
  and [@llorente2025transformer].
:::

# System Implementation {#ch:system-implementation}

## Scope and approach

### Scope of this chapter

This chapter documents the system built around the forecasting models.
That system comprises the orchestration layer, infrastructure choices,
tech stack, and CI/CD pipeline that together let the platform run
reliably in production. Operational material such as running backfills,
adding new bidding zones, or re-deploying Prefect flows is kept in the
repository's `RUNBOOK.md` and `CONTRIBUTING.md` and is not repeated
here.

### Structuring the chapter around Zarour's practices

The chapter is organised around the nine MLOps practices identified in
the systematic literature review by Zarour et al. [@zarour2025]. These
are automating CI/CD, orchestrating workflows, ensuring reproducibility,
versioning, collaboration and communication, continuously training and
evaluating models, tracking and logging ML metadata, continuous
monitoring, and implementing feedback loops. Each practice section
follows a fixed shape. It gives Zarour's own framing of the practice and
what it requires of a production ML system, the concrete implementation
found in algo-repo, the technology chosen together with the alternatives
that were considered and rejected, and the design rationale given the
single-host MVP scope of the platform. This structure makes it
straightforward to assess which practices are fully implemented,
partially implemented, or deferred, and to trace every technology choice
back to an explicit justification. The same nine practice structures the
maturity assessment in
Chapter [7](#ch:results-system){reference-type="ref"
reference="ch:results-system"}.

## System at a Glance

### Host-level architecture

The platform runs entirely within a single Docker Compose stack on one
dedicated host, keeping operational complexity proportionate to the MVP
scope. The system consists of six services that runs constantly.
ClickHouse stores all time-series data and ML artefacts. The Prefect
server exposes the orchestration API and web UI. The Prefect worker
polls for scheduled runs and manages a Docker work pool. Loki receives
structured log streams from Python via `python-logging-loki`, and
Prometheus scrapes service metrics from ClickHouse and Grafana. Grafana
visualises the ClickHouse data, the Loki log stream, and the Prometheus
series through dashboards. When the Prefect worker dispatches a
scheduled flow run, it spawns an ephemeral container from the
`algo-repo:latest` image. That container reads from and writes to
ClickHouse, calls the ENTSO-E Transparency Platform API, and produce a
structured logs back to Loki before being removed automatically on
completion.

<figure id="fig:f1-architecture" data-latex-placement="h">
<span class="image placeholder"
data-original-image-src="f1-architecture" data-original-image-title=""
width="\linewidth"></span>
<figcaption>Host level architecture. A single Docker Compose host runs
the six services, namely ClickHouse, the Prefect server and worker,
Prometheus, Grafana, and Loki. Flow runs spawn ephemeral
<code>algo-repo:latest</code> containers that read and write ClickHouse,
fetch from ENTSO-E, and push logs to Loki; Prometheus scrapes service
metrics and Grafana queries Prometheus and Loki.</figcaption>
</figure>

### Data plane

Data enters the platform through the ENTSO-E Transparency Platform API,
where four fetch functions retrieve energy prices, total-load forecasts,
generation forecasts, and wind and solar forecasts for each configured
bidding zone. The raw XML responses are parsed by mapper functions that
produce `Observations` and `Forecast` domain objects, which are then
ingested into ClickHouse tables `algo.timeseries` and `algo.forecasts`
via batch inserts. Both tables use `ReplacingMergeTree` engines, which
deduplicate overtime on merge. A preprocessor loads this data, pivots it
to a daily wide feature matrix through a configurable sequence of
feature transformers, and feeds it to either the backtest engine for
offline evaluation or the live runner for day-ahead production
forecasting. Predictions and trained model artefacts are persisted to
`algo.experiment_runs`, `algo.experiment_predictions`, and
`algo.model_artifacts`, from where the reconciliation flow back fills
actuals the following day and the drift detection flow compares the
recent price distribution against a 90-day reference window, triggering
an alert and an optional automatic retraining run when significant drift
is detected. Figure [5.4](#fig:f2-data-plane){reference-type="ref"
reference="fig:f2-data-plane"} draws this path together
(§[5.4](#sec:si-crosscutting){reference-type="ref"
reference="sec:si-crosscutting"}).

### Operational inventory

Table [5.1](#tab:inventory){reference-type="ref"
reference="tab:inventory"} lists every Prefect deployment currently
registered in the system, together with its schedule, the flow it
executes, and the Zarour practice it primarily realises.

::: {#tab:inventory}
  **Deployment**                   **Area / model**    **Cron**        **Purpose**                        **Zarour**
  -------------------------------- ------------------- --------------- ---------------------------------- ------------
  entsoe-backfill-dk1              DK1                 0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  entsoe-backfill-dk2              DK2                 0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  entsoe-backfill-nl               NL                  0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  entsoe-backfill-be               BE                  0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  entsoe-backfill-de               DE                  0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  entsoe-backfill-fr               FR                  0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  entsoe-backfill-pl               PL                  0 \* \* \* \*   Hourly ENTSO-E ingest              P2
  daily-forecast-dk1_lear          DK1 / LEAR          0 6 \* \* \*    Daily refit + forecast             P6
  daily-forecast-de_lear           DE / LEAR           0 6 \* \* \*    Daily refit + forecast             P6
  daily-forecast-dk1_dnn           DK1 / DNN           0 6 \* \* \*    Daily refit + forecast             P6
  daily-forecast-de_dnn            DE / DNN            0 6 \* \* \*    Daily refit + forecast             P6
  daily-forecast-dk1_transformer   DK1 / Transformer   0 6 \* \* \*    Daily refit + forecast             P6
  daily-forecast-de_transformer    DE / Transformer    0 6 \* \* \*    Daily refit + forecast             P6
  reconcile-predictions            all                 0 18 \* \* \*   Day-after reconciliation           P7, P8
  drift-detection-dk1              DK1                 0 19 \* \* \*   Drift, 90d ref vs 7d (Evidently)   P8, P9
  drift-detection-de               DE                  0 19 \* \* \*   Drift, 90d ref vs 7d (Evidently)   P8, P9

  : Operational inventory of Prefect deployments. Cron strings are UTC;
  the seven backfill deployments and six forecast deployments are
  per-area instances of a single shared flow definition apiece.
:::

## Implementing Zarour's Nine MLOps Practices

The nine sections that follow map every MLOps practice identified by
Zarour et al. (Chapter [3](#ch:background){reference-type="ref"
reference="ch:background"}) to a concrete subsystem in algo-repo, in
Zarour's order from P1 to P9.

### P1: Automating CI/CD

Under automated CI/CD, every proposed change is validated before it
reaches `main`, and an accepted change then propagates to the running
system without manual intervention [@zarour2025]. In algo-repo this is a
two-phase GitHub Actions pipeline
(Figure [5.2](#fig:f3-cicd){reference-type="ref"
reference="fig:f3-cicd"}).

On a pull request, three checks must pass before a merge is allowed.
`pr_test` runs the full pytest mirroring `src/`, `pr_ruff-lint` runs the
`ruff` linter, and `pr_smoke` runs an end-to-end daily-forecast and
reconciliation with synthetic data. A path filter skips the expensive
smoke build for documentation only changes.

On merge to `main`, `cd_deploy` reaches the production host and, gated
by which paths changed, applies any new ClickHouse migrations, rebuilds
the `algo-repo:latest` image with the commit SHA baked in, and reruns
`deploy_ingestion.py` and `deploy_forecast.py` to register the updated
Prefect deployments. It finally triggers `daily-forecast-dk1_lear` and
polls until it completes, confirming the deployed image produces a valid
forecast on the live host. A parallel job restarts Grafana when its
provisioning changes.

<figure id="fig:f3-cicd" data-latex-placement="h">
<span class="image placeholder" data-original-image-src="f3-cicd"
data-original-image-title="" width="78%"></span>
<figcaption>The CI/CD pipeline. On a pull request, three checks
(<code>pr_test</code>, <code>pr_ruff-lint</code>, <code>pr_smoke</code>)
must pass before a merge. On merge to <code>main</code>,
<code>cd_deploy</code> reaches the host over Tailscale, rebuilds the
image, redeploys the Prefect flows, and runs a smoke
forecast.</figcaption>
</figure>

The deploy host is reached only over a Tailscale mesh. The runner joins
the tailnet for the duration of the workflow with an ephemeral key, so
the host never exposes an SSH port to the public internet. GitHub
Actions was chosen over Jenkins or CircleCI because it is co-located
with the repository and needs no separately managed runner.

### P2: Orchestrating workflows

Orchestrating workflows means expressing the recurring data and model
tasks as scheduled, observable, pipelines that retry instead of cron
driven scripts, so that failures are isolated, retried, and surfaced
rather than silently lost [@zarour2025].

All recurring work on the platform is expressed as four Prefect flows
executed by a Docker work pool
(Table [5.1](#tab:inventory){reference-type="ref"
reference="tab:inventory"}). These are ingestion, daily forecast,
reconciliation, and drift detection. Scheduling is declarative. Each
deployment in Table [5.1](#tab:inventory){reference-type="ref"
reference="tab:inventory"} attaches a cron schedule to a flow, and the
worker spawns an ephemeral `algo-repo:latest` container per run. The
ingestion flow is parameterised by area, a single flow definition with
one deployment per bidding zone, so adding a market is a one line
deployment change with no strutural code edit. Within a flow,
granularity is one task per data type, covering prices, load,
generation, and wind/solar. Tasks run sequentially to because of the
ENTSO-E rate limit and each carries `retries=2` with a 60 second delay,
so one data type failing does not abort the others. The ingestion flow
re-ingests a rolling 48-hour lookback window on every run. Because both
ClickHouse tables are `ReplacingMergeTree`, re-ingesting overlapping
data is always safe.

The fetch and insert logic lives in a shared ingest service with no
Prefect dependency, so both the data-backfill CLI and the ingestion flow
import the same code path instead of duplicating it. Prefect was
preferred to Airflow and Dagster. At single host scale its Python native
flow definitions and Docker work pool suffice, and it avoids the
operational weight of an Airflow scheduler or a Dagster daemon and
database.

### P3: Ensuring reproducibility

In MLOps, reproducibility is about reconstructing a past model result
from the same code version, data window, hyperparameters, and runtime
environment, without relying on implicit host state [@zarour2025].
Zarour et al. identify it as one of the most frequently cited challenges
in practitioner surveys, and identify runtime containerisation as a key
way to fix it.

The platform addresses reproducibility along three axes. First, the
runtime is fully containerised. The entire operational stack, comprising
all six services with their volumes, environment, and network, is
declared in `docker-compose.yml`. The flow run and worker containers are
built from `Dockerfile` and `Dockerfile.worker`, and Grafana's
provisioning, the alert rules, and the Prometheus scrape config are all
from the repository. The infrastructure can therefore be rebuilt from
the repository alone, with no manually typed host commands. Second,
every row in `algo.experiment_runs` records its git SHA and the data
window it used, which together fix the code version and the data behind
any run. The `GIT_SHA` is baked into the image at build time rather than
resolved at runtime, because the deploy host holds only the built image
and not the source tree, and local runs emit an empty string so a dirty
tree never stamps a misleading SHA. Third, the modelling pipeline is
driven entirely by the committed config. The calibration windows and the
`AsinhScaler` target transform are fixed there, and the DNN ensemble
averages `n_dnn_ensemble` replicates with distinct, enumerated random
seeds, so the training inputs and seed sequence are fully pinned. LEAR
is deterministic and reproduces to solver tolerance, while the deep
models' controlled re-run is left to future work, since GPU-kernel
non-determinism is not yet suppressed
(§[7.2](#sec:res-repro){reference-type="ref"
reference="sec:res-repro"}).

Docker Compose, not Kubernetes, runs the container runtime. At single
host scope, a control plane, etcd, and Helm charts are unjustified
overhead (§[5.4](#sec:si-crosscutting){reference-type="ref"
reference="sec:si-crosscutting"}). Baking the SHA into the image rather
than resolving it at container start makes every `algo.experiment_runs`
row self describing under a deployment model that has no source checkout
on the host.

### P4: Versioning

Versioning underpins every other practice. All code, data schemas, and
configuration that affect model behaviour are tracked in source control,
so any past system state can be reconstructed [@zarour2025]. Zarour et
al. treat it as a prerequisite, because without a shared history of code
and configuration changes, claims about reproducibility or rollback
cannot be substantiated.

The platform uses Git with GitHub as the remote, and versions every
artefact that can affect a model run. Python experiment configs in
`configs/` are Git files whose history records every calibration window
or scaler change. ClickHouse schema changes live in numbered SQL
migration files under `src/infrastructure_clickhouse/migrations/` that
are auto discovered in sorted order by `run_migrations.py` and never
modified retroactively. Grafana dashboard definitions and alert rules,
stored as JSON and YAML under `grafana/`, are file provisioned, never
edited through the UI, and subject to code review before taking effect.

DVC was evaluated for data versioning and rejected. ENTSO-E data is
replayable in full from the public API and not expendsive to retrieve,
and combining ClickHouse's `ReplacingMergeTree` engine with the
`git_sha` column on `algo.experiment_runs` provides sufficient
provenance without maintaining a separate binary store. Every artefact
that affects model output is kept under version control. A single
`git log` therefore covers the experiment, the infrastructure, and the
alerting policy together, so every operational change is recorded in one
audit trail, as a production ML system requires.

### P5: Collaboration and communication

Collaboration practices let contributors work on a shared ML system
without relying on tribal knowledge [@zarour2025]. As a single developer
project this was the least emphasised of the nine practices, but the
core disciplines were still followed. Every code change went through a
GitHub pull request rather than a direct commit to `main`, so each
change passed the CI gate of P1
(Figure [5.2](#fig:f3-cicd){reference-type="ref"
reference="fig:f3-cicd"}) and left a reviewable record of what changed
and why. GitHub Issues tracked outstanding work and the status of each
feature branch, giving a single queue of what was in progress, blocked,
or done.

Beyond the version-control workflow, project conventions, repository
structure, and operational procedures are kept in versioned Markdown
files, `docs/REPO_OVERVIEW.md`, `docs/RUNBOOK.md`, and
`docs/CONTRIBUTING.md`, so the design rationale and the onboarding path
for a future contributor live in the repository itself rather than in
any one person's head.

### P6: Continuously train and evaluate

Continuous training and evaluation retrains the model automatically on a
regular cadence so that it reflects the most recent data distribution,
and scores its live predictions against realised outcomes as they arrive
[@zarour2025]. Zarour et al. distinguish the scheduled, unconditional
refit from the reactive drift-triggered path of P9.

The platform's train-and-evaluate cycle runs on a fixed daily cadence
(Figure [5.3](#fig:p6-cadence){reference-type="ref"
reference="fig:p6-cadence"}). The six `daily-forecast-*` deployments,
covering LEAR, DNN, and Transformer for both DK1 and DE, execute the
daily-forecast flow at 06:00 UTC. Each run invokes the live runner,
which loads the latest ClickHouse data window, refits the ensemble of
calibration-window models from scratch, and immediately produces a
day-ahead forecast. For DNN configurations it fits `n_dnn_ensemble` seed
replicates and averages them, following Lago et al. [@lago2021]. The
trained models are serialised to `algo.model_artifacts`. The evaluation
half of the practice is the reconciliation flow (P7--P8). The day after
each forecast, realised prices are joined to the stored predictions and
the same MAE, RMSE, and sMAPE used in backtesting are computed on the
live forecast, so offline and online evaluation use one metric
implementation.

<figure id="fig:p6-cadence" data-latex-placement="h">
<span class="image placeholder"
data-original-image-src="f5-daily-cadence" data-original-image-title=""
width="92%"></span>
<figcaption>The daily train-and-evaluate cadence (UTC). At 06:00 every
configuration refits from scratch and produces a day-ahead forecast; at
18:00 reconciliation joins the published actuals to the stored
predictions and scores them; at 19:00 drift detection runs. The cycle
repeats every day.</figcaption>
</figure>

A full refit from scratch on each run was chosen over warm-start
learning. The daily data increment is small relative to the calibration
windows, so a clean refit is cheap and avoids accumulated approximation
error. Keeping training and prediction in one flow means a single
task-level retry covers both phases and the served model is always
consistent with the forecast it produced.

### P7: Track and log ML metadata

Tracking and logging ML metadata records the full provenance of every
model run in a queryable store, so that past results can be reproduced
and compared without ad-hoc file management [@zarour2025]. That
provenance covers the hyperparameters, data windows, performance
metrics, and the model artefact itself.

This is handled in ClickHouse. `algo.experiment_runs` stores a
self-describing row per run, holding its training duration, data window,
git SHA, and a link to the stored model. `algo.experiment_predictions`
holds one row per period per day for reconciliation,
`algo.model_artifacts` stores the serialised models as blobs, and
`algo.hyperparam_trials` persists every Optuna trial for resumable
search. On the research surface, W&B hosts two projects, `algo-research`
for backtests and sweeps and `algo-prod` for production reconciliation;
`WANDB_MODE=disabled` no-ops it in CI and local development.

A filesystem model store was rejected. Storing artefacts as blobs in
`algo.model_artifacts` keeps them attached to the experiment row rather
than in a separately managed path. MLflow was evaluated and deferred
since W&B covered most of the functionalities needed. At the current
scale ClickHouse and W&B together cover the audit-log and
research-surface roles without adding a service to the Compose stack.
Using one OLAP store for predictions, metrics, and artefacts makes day
after reconciliation a single query, and the
`ReplacingMergeTree(created_utc)` engine makes the reconciliation update
a safe re-insert rather than a mutable `UPDATE`.

### P8: Continuous monitoring

Continuous monitoring consists of Zarour's three axes, data quality,
model performance, and system health, so that degradation surfaces
automatically rather than by manual inspection [@zarour2025].
Table [5.2](#tab:monitoring-coverage){reference-type="ref"
reference="tab:monitoring-coverage"} maps each axis to the surface that
presents it and the store it reads. Structured logs from every Prefect
flow and infrastructure module are pushed straight to Loki through a
`python-logging-loki` handler, and Grafana auto-provisions three
dashboards over ClickHouse, Prometheus, and Loki from
`grafana/dashboards/`. Grafana owns platform and data health and W&B
owns model quality, and both read from the same ClickHouse tables.

::: {#tab:monitoring-coverage}
  **Axis / role**     **Surface**               **Source**   **What it watches**
  ------------------- ------------------------- ------------ ------------------------------------------------------------------------------------------------
  Data quality        Grafana *Data Quality*    ClickHouse   Freshness, daily row counts, and missing price hours in `algo.timeseries` and `algo.forecasts`
  System health       Grafana *System Health*   Prometheus   Service uptime, scrape status, query rate, memory, and merge backlog
  Model performance   W&B `algo-prod`           ClickHouse   MAE, RMSE, and sMAPE per reconciled day, area, and config
  Operational logs    Grafana *Operational*     Loki         Log stream by `job=algo-repo`, plus error rate and logs by service

  : Monitoring coverage. The first three rows are Zarour's P8 axes;
  *Operational* is the shared structured-log stream beneath them.
  Grafana and W&B both read from ClickHouse.
:::

Five conditions raise an alert, listed in
Table [5.3](#tab:alert-rules){reference-type="ref"
reference="tab:alert-rules"}.

::: {#tab:alert-rules}
  **Alert**                 **Fires when**                                      **Severity**
  ------------------------- --------------------------------------------------- --------------
  `data-staleness`          No fresh price row in twelve hours                  warning
  `drift-detected-today`    A `drift_reports` row is flagged today              warning
  `reconciliation-missed`   No reconciled run in the last 36 hours              error
  `clickhouse-down`         `up{job="clickhouse"}` is zero for five minutes     critical
  `accuracy-degradation`    Today's MAE exceeds $1.5\times$ the 30-day median   warning

  : Alert rules and their severities. The first four are
  file-provisioned Grafana rules in
  `grafana/provisioning/alerting/rules.yaml`, evaluated over ClickHouse
  except `clickhouse-down`, which reads the Prometheus liveness metric.
  `accuracy-degradation` is a check inside the reconciliation flow.
:::

Loki was chosen over the heavier ELK stack because it runs with far
lower memory and operational overhead, proportionate to a single host
and integrates well with Grafana. Prometheus sits alongside Loki as the
metrics tier to its logs tier, scraping ClickHouse, Grafana, and itself
every 15 seconds and retaining 120 days of series, with Grafana the
single dashboard and alerting surface above both.

### P9: Implementing feedback loops

A feedback loop should detect when a system's inputs or outputs have
shifted enough to degrade quality and respond automatically, instead of
waiting for a human to notice [@zarour2025]. This is the least developed
of the nine practices on the platform and one of its weaker points.
Drift detection itself runs daily and in-process, inside the
`drift-detection-dk1` and `drift-detection-de` deployments, via
Evidently's `DataDriftPreset` comparing a 90-day reference window
against a 7-day current window on each area's price series. Every result
is written to `algo.drift_reports`, and a detected event posts a warning
to Loki and raises an alert.

The automatic response, however, is wired but inactive. A drift event
triggers a retraining run only when a forecast config sets
`retrain_on_drift=True`, which none of the six production configs does,
so the flag stays false everywhere and drift in practice serves as a
monitoring and alerting signal rather than a closed loop. The retrain
path is nonetheless implemented and auditable, namely a triggered flow
that records an audit row in `algo.retrain_events` and links the
resulting run to the `drift_report_id` that caused it. Whether closing
the loop is worthwhile at all, given the cheap daily refit that already
retrains every model from scratch, is examined in
Chapter [7](#ch:results-system){reference-type="ref"
reference="ch:results-system"}.

## Reproducibility, monitoring, and single-host scope {#sec:si-crosscutting}

With every practice now described,
Figure [5.4](#fig:f2-data-plane){reference-type="ref"
reference="fig:f2-data-plane"} draws them together into the single data
path the platform implements, from ingestion into the database, through
the forecasting pipeline that reads it, to the daily loop that closes
back onto the database.

<figure id="fig:f2-data-plane" data-latex-placement="H">
<span class="image placeholder" data-original-image-src="f2-data-plane"
data-original-image-title="" width="\linewidth"></span>
<figcaption>Data plane (high level). ENTSO-E data is ingested into
ClickHouse; the forecasting pipeline loads it, builds features, and
trains and serves the models, writing predictions and artefacts back.
The daily reconciliation-and-drift loop reads those predictions, writes
back actuals and metrics, and raises alerts or retraining.</figcaption>
</figure>

### GIT_SHA propagation as the reproducibility--monitoring link

Every row that `cd_deploy.yml` produces in `algo.experiment_runs`
carries the same `git_sha` baked into the image during the deploy-gate
build step, the SHA of the exact commit merged to `main`. The Grafana
Operational dashboard queries the Loki log stream filtered by
`job=algo-repo` and presents structured events that include the same
SHA, because every flow container is built from that image. So if the
W&B `algo-prod` run for an `(area, config_name)` shows an unexpected MAE
spike beginning on a particular day, the Operational dashboard shows the
Loki events from the same period alongside the `git_sha` of the image
that produced them, making it possible to `git log` back to the exact
commit. This links the reproducibility of P3 to the monitoring of P8.
The audit trail for a production anomaly runs from the Grafana panel,
through the `algo.experiment_runs` row, to a checkable commit.

### Why a single-host deploy is the right MVP scope

The entire stack runs on one Docker Compose host, for two reasons.
First, Kubernetes and multi host orchestration were out of scope for
this project. The operational complexity of a control plane, distributed
storage for ClickHouse, and cross host log aggregation would have slowed
iteration without improving the platform's ability to deliver daily
forecasts. Such an architecture would, however, genuinely improve
robustness, since it removes the single failure domain and enables
rolling deployments and horizontal scaling. It is the natural next step
once a second host is justified. Second, only one compute instance was
available, so a distributed deployment was not an option in any case. On
a single host the worst case is one failure domain, and rollback is
simply rebuilding the image and restarting the stack.

# Forecasting-Model Results {#ch:results-models}

This chapter reports the comparison of the three forecasting models
specified in Chapter [4](#ch:methods-models){reference-type="ref"
reference="ch:methods-models"}. Six backtests were run, covering LEAR,
the DNN, and the Transformer, each on DK1 and DE, over a single shared
hourly test window (2025-10-24 to 2026-05-31) with the same feature sets
as in the papers. Within each market the models are compared on the test
days that all of them produced. After warmup, gap, and daylight saving
days are dropped, LEAR and the DNN retain 204 test days on DK1 and 201
on DE, and the Transformer's fourteen day input sequence consumes more
leading days still, so the common set is 187 days on DK1 and 176 on DE.
The chapter reports headline accuracy
(§[6.1](#sec:rm-headline){reference-type="ref"
reference="sec:rm-headline"}), statistical significance
(§[6.2](#sec:rm-significance){reference-type="ref"
reference="sec:rm-significance"}), and computation cost
(§[6.3](#sec:rm-cost){reference-type="ref" reference="sec:rm-cost"}),
then sets the results against the published benchmarks
(§[6.4](#sec:rm-papers){reference-type="ref"
reference="sec:rm-papers"}).

## Headline accuracy {#sec:rm-headline}

::: {#tab:results-dk1-headline}
                        MAE     RMSE    sMAPE    rMAE
  ---------------- -------- -------- -------- -------
  LEAR               17.574   26.891   29.048   0.469
  DNN                17.960   25.634   29.339   0.482
  Transformer        20.076   28.909   31.767   0.543
  Naive (weekly)     36.899   51.385   50.110   1.000

  : DK1 final benchmark metrics (test 2025-10-24--2026-05-31, common
  days).
:::

::: {#tab:results-de-headline}
                        MAE     RMSE    sMAPE    rMAE
  ---------------- -------- -------- -------- -------
  LEAR               13.069   25.041   22.107   0.376
  DNN                13.476   22.544   22.763   0.388
  Transformer        14.719   23.755   23.901   0.420
  Naive (weekly)     35.049   51.914   46.090   1.000

  : DE final benchmark metrics (test 2025-10-24--2026-05-31, common
  days).
:::

Tables [6.1](#tab:results-dk1-headline){reference-type="ref"
reference="tab:results-dk1-headline"}
and [6.2](#tab:results-de-headline){reference-type="ref"
reference="tab:results-de-headline"} report the four accuracy metrics on
the common test days. The ordering is the same in both markets and
across MAE, rMAE, and sMAPE. LEAR is the most accurate, the DNN follows
closely, and the Transformer is third, with all three improving
substantially on the weekly-naive baseline. The rMAE values are 0.469
(LEAR), 0.482 (DNN), and 0.543 (Transformer) on DK1, and 0.376, 0.388,
and 0.420 respectively on DE. Because rMAE normalises each model against
the same-market naive error, these figures are comparable across
markets. All three models sit markedly further below 1 on DE than on
DK1, indicating that the German price was the more predictable of the
two relative to its own naive benchmark over this window.

The single metric that reorders the models is RMSE. The DNN got the
lowest RMSE in both markets (25.6 against LEAR's 26.9 on DK1, and 22.5
against 25.0 on DE), and on DE LEAR got the highest RMSE of the three,
behind the Transformer. As RMSE weights large deviations more heavily
than MAE, this is evidence that the DNN suppresses the largest forecast
errors more effectively than LEAR even on the days where LEAR's mean
error is slightly lower. LEAR's advantage is thus specific to the
absolute error metrics that Lago et al. [@lago2021], §5.4, designate as
primary. On the squared error criterion the DNN is preferable. Whether
either difference is statistically meaningful is the subject of
§[6.2](#sec:rm-significance){reference-type="ref"
reference="sec:rm-significance"}.

Figure [6.3](#fig:rm-forecast-week){reference-type="ref"
reference="fig:rm-forecast-week"} makes these orderings concrete and
explains the Transformer's standing. It contrasts a calm low renewable
week, in which all three models track the price closely, with a high
renewable week in late May whose negative price hours and sharp peak the
Transformer smooths over while LEAR and the DNN follow them. The effect
is not merely that volatile weeks carry larger prices. Relative to the
weekly-naive baseline, LEAR's and the DNN's monthly rMAE stays roughly
flat across the window, whereas the Transformer's climbs in the
renewable-heavy months, reaching 0.92 on DK1 in May, which is what
accounts for its third place.
Figure [6.6](#fig:rm-mae-hour){reference-type="ref"
reference="fig:rm-mae-hour"} breaks the error down by hour of day.

<figure id="fig:rm-forecast-week" data-latex-placement="h">
<figure id="fig:rm-forecast-calm">
<span class="image placeholder"
data-original-image-src="forecast_calm_dk1" data-original-image-title=""
width="\linewidth"></span>
<figcaption>Calm low-renewable week (2–8 February 2026)</figcaption>
</figure>
<p><br />
</p>
<figure id="fig:rm-forecast-renew">
<span class="image placeholder"
data-original-image-src="forecast_renew_dk1"
data-original-image-title="" width="\linewidth"></span>
<figcaption>Volatile high-renewable week (25–31 May 2026)</figcaption>
</figure>
<figcaption>DK1 day-ahead forecasts against realised prices in a calm
low-renewable week and a volatile high-renewable week, with vertical
lines marking day boundaries and the grey line at zero. In the calm week
all three models track the price closely. In the high-renewable week,
with negative-price hours and a sharp scarcity peak, the Transformer
smooths over both extremes while LEAR and the DNN follow
them.</figcaption>
</figure>

<figure id="fig:rm-mae-hour" data-latex-placement="H">
<figure id="fig:rm-mae-hour-dk1">
<span class="image placeholder"
data-original-image-src="mae_by_hour_dk1" data-original-image-title=""
width="\linewidth"></span>
<figcaption>DK1</figcaption>
</figure>
<figure id="fig:rm-mae-hour-de">
<span class="image placeholder" data-original-image-src="mae_by_hour_de"
data-original-image-title="" width="\linewidth"></span>
<figcaption>DE</figcaption>
</figure>
<figcaption>Mean absolute error by hour of day across the full test
window (2025-10-24 to 2026-05-31). Error is smallest overnight and
largest on the morning and evening ramps, and the Transformer’s error
exceeds LEAR’s and the DNN’s at most periods.</figcaption>
</figure>

## Statistical significance {#sec:rm-significance}

<figure id="fig:rm-gw" data-latex-placement="h">
<figure id="fig:rm-gw-dk1">
<span class="image placeholder" data-original-image-src="gw_heatmap_dk1"
data-original-image-title="" width="\linewidth"></span>
<figcaption>DK1</figcaption>
</figure>
<figure id="fig:rm-gw-de">
<span class="image placeholder" data-original-image-src="gw_heatmap_de"
data-original-image-title="" width="\linewidth"></span>
<figcaption>DE</figcaption>
</figure>
<figcaption>Giacomini–White multivariate p-values, one heatmap per
market. Cell <span class="math inline">(<em>r</em>, <em>c</em>)</span>
is the pairwise p-value that column model <span
class="math inline"><em>c</em></span> is no more accurate than row model
<span class="math inline"><em>r</em></span>, shaded on a continuous
scale from green at <span class="math inline"><em>p</em> = 0</span> to
red at <span class="math inline"><em>p</em> = 1</span>, with the value
printed in each cell and the undefined diagonal shown as
<code>--</code>. A value below 0.05 marks a significant win for <span
class="math inline"><em>c</em></span> over <span
class="math inline"><em>r</em></span>. LEAR and the DNN are
indistinguishable, both significantly beat the Transformer, and every
model beats the weekly-naive baseline.</figcaption>
</figure>

The Giacomini--White multivariate test [@giacomini2006gw; @lago2021]
establishes whether these differences are significant.
Figure [6.9](#fig:rm-gw){reference-type="ref" reference="fig:rm-gw"}
gives the pairwise p-values, where cell $(r,c)$ is the probability of a
loss differential at least as large as the one observed under the null
that column model $c$ is no more accurate than row model $r$ (the
convention of [@lago2021], Fig. 5). A value below 0.05 means that $c$
significantly outperforms $r$.

The central result is that LEAR and the DNN are statistically
indistinguishable on both markets. The hypothesis that LEAR is no more
accurate than the DNN cannot be rejected (DK1 $p=0.16$, DE $p=0.19$).
LEAR's numerical lead in the headline tables therefore does not amount
to a significant accuracy advantage, and on this test window neither
model can be shown to be the more accurate. Both, however, significantly
outperform the Transformer (on DK1 at $p=0.001$ for each, and on DE at
$p=0.012$ for LEAR and $p=0.006$ for the DNN), and all three beat the
weekly-naive baseline with $p\approx0$. The comparison that survives
significance testing is thus a two-way tie between LEAR and the DNN at
the top, a significantly weaker Transformer, and a baseline that every
model clears by a wide and significant margin, consistently across DK1
and DE.

## Computation cost {#sec:rm-cost}

::: {#tab:results-cost}
  **Model**       **DK1 s/day**   **DE s/day** **Hardware / cadence**
  ------------- --------------- -------------- -------------------------------------------------------
  LEAR                     50.3           41.3 CPU, one LassoCV per period $\times$ 3 windows, daily
  DNN                       0.9            1.6 GPU, one MIMO net (single seed), daily
  Transformer               1.6            1.9 GPU, one MIMO net, weekly refit

  : Amortised recalibration cost (full-backtest wall-clock / common test
  day). Full timings in `Report/metrics/run_timings.md`.
:::

Table [6.3](#tab:results-cost){reference-type="ref"
reference="tab:results-cost"} reports the amortised recalibration cost,
the full-backtest wall-clock divided by the number of common test days,
for each model and market. The figures invert the cost ordering of Lago
et al. [@lago2021], Table 4, where on hourly CPU hardware LEAR trains in
seconds and the DNN in minutes. Here the relationship is reversed. The
GPU-trained MIMO networks recalibrate in one to two seconds per day,
whereas LEAR (which fits an independent cross-validated Lasso for each
of the 24 delivery periods across three calibration windows, entirely on
CPU) takes forty to fifty. The DNN is therefore roughly 25 to 55 times
cheaper per recalibration than LEAR while, as
§[6.2](#sec:rm-significance){reference-type="ref"
reference="sec:rm-significance"} showed, being its statistical equal in
accuracy. This inversion is a property of the hardware rather than of
the models or the markets, since a GPU rewards the dense neural networks
and penalises LEAR's many small per-period fits. The Transformer,
refitted weekly, carries a comparably low amortised cost but does not
convert it into competitive accuracy.

## Comparison with published benchmarks {#sec:rm-papers}

A direct comparison of error levels with the source papers is
complicated by the shift in price regime. The benchmarks of Lago et
al. [@lago2021] were struck on 2016--2018 data, whereas this study
covers 2025--2026, so the comparison is read through model rankings
rather than absolute errors ([@lago2021], §5.4).

The rankings invert both source papers. Lago et al. [@lago2021] report
the DNN as at least the equal of LEAR, and Llorente and
Portela [@llorente2025transformer] report their Transformer ahead of the
DNN. The ordering here is the reverse on both counts, LEAR $\ge$ DNN
$\ge$ Transformer. As §[6.2](#sec:rm-significance){reference-type="ref"
reference="sec:rm-significance"} showed, the LEAR--DNN inversion is only
numerical, since the two are statistically tied, which is itself
consistent with Lago et al.'s observation that the gap is often
insignificant. The Transformer's third place, by contrast, is genuine
and significant. The likeliest cause is that the deep models are
under-optimised relative to LEAR in this study rather than inherently
weaker. The DNN was given 30 tuning trials against the paper's 1500, and
the Transformer reused the paper's Nord Pool hyperparameters without
per-market retuning and was adapted into the rolling-refit pipeline
rather than run in its native train-once-and-renormalise mode
(Chapter [4](#ch:methods-models){reference-type="ref"
reference="ch:methods-models"},
Table [4.3](#tab:mm-deviations){reference-type="ref"
reference="tab:mm-deviations"}), while LEAR re-selects its penalty by
cross-validation at every recalibration and so sits near its achievable
best.

# System Evaluation Results {#ch:results-system}

This chapter evaluates the system. The forecast accuracy results are in
Chapter [6](#ch:results-models){reference-type="ref"
reference="ch:results-models"}. Following the single case study
guidelines of Runeson and Höst [@runeson2009casestudy], the system is
evaluated from its source code, version control and CI history, the
ClickHouse experiment tracker, and short targeted experiments. The
figures are indicative of the system over the study window rather than
claims about long run production operation, a framing that matches
comparable MLOps evaluations in the electricity forecasting
domain [@subramanya2022devops2mlops].

The evaluation composes three established methods introduced in
§[3.5](#sec:bg-eval){reference-type="ref" reference="sec:bg-eval"}, two
objective measurements and one structured self assessment. An objective
measurement is a number a script recomputes on demand from code, git
history, or the database, via `scripts/report/extract_metrics.py` and
`reproduce_run.py`. The self assessment is the ML Test Score, a one line
of evidence a reader can check or contest. The maturity placement of
§[7.4](#sec:res-maturity){reference-type="ref"
reference="sec:res-maturity"} then positions all nine of Zarour et al.'s
practices [@zarour2025] against this evidence and the system chapter
(Chapter [5](#ch:system-implementation){reference-type="ref"
reference="ch:system-implementation"}). Each method is applied below and
its result reported.

## ML Test Score {#sec:res-mlts}

The ML Test Score rubric of Breck et al. [@breck2017mltestscore] scores
28 tests across four sections on a $\{0, 0.5, 1\}$ scale, the final
score being the minimum of the four section sums so that the weakest
area bounds the result. Table [7.1](#tab:res-mlts){reference-type="ref"
reference="tab:res-mlts"} reports the per-section sums. The full
per-item evidence is in
Appendix [11](#app:mlts-worksheet){reference-type="ref"
reference="app:mlts-worksheet"}.

::: {#tab:res-mlts}
  **Section (max 7)**         **Sum**
  ------------------------- ---------
  Data tests                      2.5
  Model development tests         3.0
  ML infrastructure tests         4.0
  Monitoring tests                4.0
  **ML Test Score (min)**     **2.5**

  : ML Test Score self-assessment (min-of-sections rule). Per-item
  evidence in Appendix [11](#app:mlts-worksheet){reference-type="ref"
  reference="app:mlts-worksheet"}.
:::

The final score is **2.5**, bound by the data-testing section. On Breck
et al.'s interpretation scale this falls in the $(2,3]$ band, a system
that is reasonably tested but could automate more of its tests and
procedures. Within the data section the system scores for enforcing
strict input schemas (`enforce_schema`) and for a tested
feature-transformer pipeline, but does not formally document the feature
benefit, feature cost, or privacy analyses the rubric also rewards, and
has no data quality CI gate. This is the system's primary remaining
investment area. The score is conservative. One data item, that all
features are beneficial, could be argued to 0.5 on two grounds, namely
that the Lasso performs feature selection and that the feature set is
grounded in Lago et al. [@lago2021]. Either argument would lift the data
section to 3.0 and the headline to 3.0. The item is left at zero absent
a documented analysis, so the reported score is a lower bound.

## Reproducibility {#sec:res-repro}

Reproducibility is reported in two senses, namely provenance coverage
across all runs and a worked re-run of one. The framing follows
Gundersen and Kjensmo [@gundersen2018reproducibility].

::: {#tab:res-repro-coverage}
  **Provenance component**             **Coverage**
  -------------------------- ----------------------
  `git_sha`                        66.7 % (10 / 15)
  `data_start_utc`                100.0 % (15 / 15)
  `data_end_utc`                  100.0 % (15 / 15)
  `model_artifact_id`             100.0 % (15 / 15)
  **Full set (all four)**      **66.7 % (10 / 15)**

  : Provenance coverage across 15 live runs in the window.
:::

Of the 15 live runs in the window, 66.7 % carry the complete provenance
set (Table [7.2](#tab:res-repro-coverage){reference-type="ref"
reference="tab:res-repro-coverage"}). The shortfall is entirely on
`git_sha`. The data-window and artefact columns are populated for every
run from day one, while five early runs predate the CD pipeline that
bakes `GIT_SHA` into the production image. From the first cd-deployed
run onward, all four components are present.

For the demonstration, the only inputs supplied were the run's committed
config `dk1_lear` and its target date 2026-03-22, from which
`scripts.report.reproduce_run` regenerated the forecast and compared it
against the stored prediction in `algo.experiment_predictions`. For this
deterministic LEAR configuration the maximum absolute difference across
all 24 delivery periods was $7\times10^{-6}$ EUR/MWh, far below any
economically meaningful price unit, so the regenerated and stored
forecasts are numerically identical with an acceptable tolerance. LEAR
is used for the headline demonstration because it is deterministic given
a fixed data window. The DNN and Transformer carry seed and ensemble
stochasticity whose controlled re-run is left to future work. Beyond any
single run, the runtime environment is pinned in `uv.lock` and the full
stack is declared as in `docker-compose.yml`, so the platform that
produced these results can be rebuilt from the repository alone.

## Drift detection as monitoring, not a retraining trigger {#sec:res-drift}

The system refits every model from scratch daily on a rolling window at
a cost of seconds
(Chapter [5](#ch:system-implementation){reference-type="ref"
reference="ch:system-implementation"}, P6), so it is never stale between
refits, and drift triggered retraining would add no freshness benefit,
following the cost aware argument of Mahadevan and
Mathioudakis [@mahadevan2024costaware]. Drift detection is therefore
kept as a monitoring and alerting signal rather than a retraining
trigger, and `retrain_on_drift` defaults to false. Over the window the
detector flagged drift on 49 of 49 reports, an uninformatively high rate
that calls for recalibration.

## Maturity placement {#sec:res-maturity}

The platform is positioned against the Google three level maturity
model [@google_mlops_maturity]. Of the five models reviewed by Zarour et
al. [@zarour2025], Google is chosen because its three levels match the
granularity of a single host MVP, because its top level of
CI/CD-pipeline automation is plausibly attainable where Microsoft's
Level 4 of full automated operations would require multi environment
claims the platform does not make, and because it is the most cited
maturity reference in that review, giving the assignment an external
touchpoint. Table [7.3](#tab:maturity){reference-type="ref"
reference="tab:maturity"} assigns a status and a Google level to each of
Zarour's nine practices, with one line of evidence apiece. The three
status labels map to the evidence already presented. A practice is
*Realised* when a concrete, production running artefact closes it
end-to-end, and *Minimal* when the mechanism exists but its scope is
limited by design. Eight of the nine are Realised. The exception, P9 the
feedback loop, is Minimal, since drift triggered retraining exists but
is scoped to two areas behind an opt-in flag, consistent with the
monitoring not trigger argument of
§[7.3](#sec:res-drift){reference-type="ref" reference="sec:res-drift"}.
The levels themselves are descriptive ordinals and support positioning
rather than measurement. The quantitative load is carried by the ML Test
Score and reproducibility results above.

::: {#tab:maturity}
  **Practice**                       **Status**    **Level**  **One-line evidence**
  ---------------------------------- ------------ ----------- ------------------------------------------------------------------------------------------------------------------------------------------------------
  P1 Automating CI/CD                Realised          2      `pr_test` / `pr_ruff-lint` / `pr_smoke` PR gates, `cd_deploy` on every merge to `main`
  P2 Orchestrating workflows         Realised          2      Prefect flows with per-area deployments on a Docker work pool
  P3 Ensuring reproducibility        Realised          2      `GIT_SHA` + data-window columns per run, containerised runtime in `docker-compose.yml`
  P4 Versioning                      Realised          2      Git tracks `configs/`, numbered migrations, dashboards and alert rules all version-controlled
  P5 Collaboration & communication   Realised          1      `REPO_OVERVIEW.md`, `RUNBOOK.md`, `CONTRIBUTING.md`
  P6 Continuously train & evaluate   Realised          1      Six `daily-forecast` deployments refit at 06:00 UTC, reconciliation scores live forecasts
  P7 Track & log ML metadata         Realised          1      `algo.experiment_runs` + predictions + artefacts, plus the W&B research surface
  P8 Continuous monitoring           Realised          2      Loki plus three Grafana dashboards (Data Quality, Operational, System Health) and four file-based alert rules, with model metrics in W&B `algo-prod`
  P9 Implementing feedback loops     Minimal           1      Drift-triggered retrain behind a config flag, two areas only

  : Maturity assessment of Zarour's nine practices, with the Google
  MLOps maturity model level [@google_mlops_maturity] assigned to each.
:::

# Discussion {#ch:discussion}

This chapter answers the three research questions of
Chapter [2](#ch:introduction){reference-type="ref"
reference="ch:introduction"} and then draws the forecasting and system
threads together. The forecasting answer (RQ1) rests on results reported
in Chapter [6](#ch:results-models){reference-type="ref"
reference="ch:results-models"}. The engineering and maturity answers
(RQ2, RQ3) synthesise the system implementation and its evaluation.

## RQ1, Comparing the forecasting models

The head-to-head comparison of LEAR, the DNN, and the Transformer across
DK1 and DE is reported in
Chapter [6](#ch:results-models){reference-type="ref"
reference="ch:results-models"}, on a single shared test window with
paired Giacomini--White tests, and against both a weekly-naive baseline
and the rankings of Lago et al. [@lago2021] and Llorente and
Portela [@llorente2025transformer]. Because the source papers' test
periods predate the present price regime, the comparison is read through
rMAE and model rankings rather than absolute errors.

Across both bidding zones the three models fall into two tiers. LEAR
records the lowest mean absolute error, and with it the lowest rMAE and
sMAPE, on both DK1 and DE (rMAE 0.469 and 0.376). The DNN follows
closely (0.482 and 0.388), and the Transformer is third (0.543 and
0.420), with all three improving a lot on the weekly-naive baseline. The
Giacomini--White test, however, cannot distinguish LEAR from the DNN on
either market. The hypothesis that LEAR is no more accurate than the DNN
gives $p=0.16$ on DK1 and $p=0.19$ on DE. LEAR's numerical lead is
therefore not a significant accuracy advantage, and over this window
neither model can be shown to be the more accurate. The same test
confirms that LEAR and the DNN each significantly outperform the
Transformer ($p\le0.013$) and that every model beats the naive forecast
($p\approx0$). The answer to RQ1 is thus a statistical tie between LEAR
and the DNN at the top, a significantly weaker Transformer, and a wide,
significant margin over the naive benchmark, which is the case for both
DK1 and DE.

The ranking depends on the error metric. As
§[6.1](#sec:rm-headline){reference-type="ref"
reference="sec:rm-headline"} showed, the DNN attains the lowest RMSE in
both markets while LEAR leads on the absolute-error measures, so the DNN
controls the worst misforecasts better than LEAR even where its mean
error is marginally larger, a distinction that matters whenever large
individual errors are disproportionately costly. The accuracy tie does
not extend to cost. On the platform's GPU the DNN recalibrates in about
a second per day against LEAR's forty to fifty
(Table [6.3](#tab:results-cost){reference-type="ref"
reference="tab:results-cost"}), so it delivers statistically equal
accuracy for far less compute. Where two models are tied on accuracy,
this asymmetry favours the DNN.

Measured against the source papers, the comparison replicates one result
and inverts two. It reproduces the finding of Lago et al. [@lago2021]
that the accuracy gap between LEAR and the DNN is frequently
insignificant. Here the two are statistically tied. It does not
reproduce the papers' point rankings. Lago et al. place the DNN at least
level with LEAR, yet here LEAR is numerically ahead (though tied), and
Llorente and Portela [@llorente2025transformer] place their Transformer
above the DNN, yet here the Transformer is significantly the weakest
model. The explanation is more likely procedural than architectural. The
deep models were optimised far less than LEAR in this study. The DNN was
tuned for 30 TPE trials against the paper's 1500, and the Transformer
reused the paper's Nord Pool hyperparameters without per market
retuning, adapted into the rolling calibration-window and weekly-refit
pipeline of the other models rather than its native train once and-
enormalise scheme (Chapter [4](#ch:methods-models){reference-type="ref"
reference="ch:methods-models"},
Table [4.3](#tab:mm-deviations){reference-type="ref"
reference="tab:mm-deviations"}). LEAR, by contrast, re-selects its
penalty by cross-validation at every daily recalibration and so has
little remaining tuning headroom. The inversion is therefore better read
as a measure of how much tuning the deep models need to express their
reported advantage than as evidence that their architectures are weaker.
Narrowing that gap is the leading item of modelling future work
(Chapter [9](#ch:conclusion){reference-type="ref"
reference="ch:conclusion"}).

## RQ2, Engineering trade-offs of productionising an EPF benchmark

Implementing the benchmark models in a scheduled, containerised pipeline
showed a series of trade offs, each resolved in favour of the
single-host MVP scope. The most consequential is the choice of a full
refit from scratch on every daily run over warm start or incremental
learning. Because the daily data increment is small relative to the
calibration windows, a clean refit is cheap and avoids accumulated
approximation error, and, as RQ3 and the drift discussion show, it also
makes the model fresh enough that drift triggered retraining becomes
redundant. Locating training and prediction in a single Prefect flow
trades a small amount of recomputation, but it makes sure that the
served model always matches the forecast it produced. Using ClickHouse
as the single store for time series, predictions, metrics, and model
artefacts makes day after reconciliation one query rather than a cross
system join, at the cost of a base64-blob artefact representation that
will not scale to large weights. And serving the paper strict feature
set in production, rather than a separate, richer operational feature
set, keeps the deployed models bit faithful to the benchmark, at the
cost of forgoing features that might help operationally but would break
the replication. In most cases the needs of a faithful benchmark and of
a small production platform lined up, both favouring simplicity,
determinism, and a single source of truth.

## RQ3, Critical practices and the limits of a single-host platform

Of Zarour's nine practices, eight are realised end-to-end and one, the
feedback loop, is minimally realised
(Table [7.3](#tab:maturity){reference-type="ref"
reference="tab:maturity"}). The quantitative evaluation shows the
binding constraint. The ML Test Score of 2.5 is bound by the data
testing section, not by infrastructure or monitoring, which both score
higher. In other words, for this platform the practices that proved
easiest to realise to a high level were the DevOps ones (CI/CD
automation, versioning, containerised reproducibility, and monitoring),
because they transfer directly from software engineering, whereas the
ML-specific data quality discipline (feature-benefit, feature-cost, and
slice analyses) is where the platform is weakest and where further
development would most have the largest outcome towards maturity.
Monitoring carries one qualification of its own. The drift detector
flagged every report over the window
(§[7.3](#sec:res-drift){reference-type="ref"
reference="sec:res-drift"}), so although the practice is wired
end-to-end its drift signal is currently uninformative and needs
recalibration. The practices that proved most critical, by contrast,
were reproducibility and metadata tracking, since the provenance they
provide is what lets any forecast be reconstructed and audited, and it
is on that provenance that the platform showed its strengths. The
single-host scope reaches its limit at three points. The artefact store
suits LEAR's small sized blobs but not bigger giga/megabyte weights.
There is no model quality gate before serving, and forecasting and drift
reach only two of the seven ingested bidding zones.

## Tying the threads together

The two threads system and modeling are closely connected and not
independent. Several modelling decisions are only defensible because of
the system around them. Downsampling both markets to an hourly grid
validates the cross market and cross paper comparison, and the cheap,
scheduled daily refit caused the drift detection to be more as a
monitoring tool rather than as a retraining trigger. The system also
claims that any forecast can be reconstructed from its logged
provenance, which is what makes the forecasting replication itself
reliable. Re-running a logged LEAR forecast reproduced it to within
$7\times10^{-6}$ EUR/MWh (§[7.2](#sec:res-repro){reference-type="ref"
reference="sec:res-repro"}), a result that speaks to the modelling work
as much as the system itself. The forecasting puts the platform through
real operating conditions, and the platform's provenance logging is what
lets those forecasts be checked and re-run.

## Limitations

On the modelling side, the test window is 31 weeks rather than the one
to two years the source papers recommend, a consequence of the data
history. The DNN hyperparameters are tuned on an architecture only
search space, with Lago's ten binary feature selector hyperparameters
left as fixed config decisions because the preprocessor exposes no
toggles for them. The Transformer reuses the paper's search range
defaults rather than per market optima, and each deep model is evaluated
from a single seeded backtest run, so its result carries the variance of
one draw, which could explain why the Transformer model performed worst.
The work forecasts spot prices, not probabilistic distributions. On the
system side, the evaluation is a single case study with no controlled
comparison, the ML Test Score is self administered and mitigated by the
per item evidence in
Appendix [11](#app:mlts-worksheet){reference-type="ref"
reference="app:mlts-worksheet"}, forecasting and drift cover only DK1
and DE, the ClickHouse blob artefact store will not scale to large
neural weights, and the drift detector over flags. These are revisited
as concrete future work in
Chapter [9](#ch:conclusion){reference-type="ref"
reference="ch:conclusion"}.

# Conclusion and Future Work {#ch:conclusion}

This thesis took the benchmark electricity-price-forecasting models from
the research literature and implemented them in a production platform
built along MLOps principles, then evaluated the result on two axes, the
forecast quality of the models and the operational maturity of the
system serving them.

On the system axis, eight of Zarour et al.'s nine MLOps
practices [@zarour2025] are realised end-to-end in the platform, and
one, the feedback loop, is minimally realised. Every realised practice
is traced to a concrete repository artefact, namely a Prefect
deployment, a ClickHouse migration, a GitHub Actions workflow, or a
Grafana dashboard. The qualitative "realised" labels are backed by
measured values, each recomputable on demand from the live system. They
comprise an ML Test Score of 2.5 bound by data testing, and provenance
coverage of 100 % from the first continuously deployed run, 66.7 %
across the full window, supported by a re-run that reproduced a logged
forecast to within $7\times10^{-6}$ EUR/MWh. Implementing the models
also exposed the engineering trade offs this raised, which mostly
aligned the demands of a faithful benchmark with those of a small
production platform. On the forecasting axis, the replication of LEAR,
the DNN, and the Transformer across DK1 and DE, evaluated with paired
significance tests on a shared recent window, is reported in
Chapter [6](#ch:results-models){reference-type="ref"
reference="ch:results-models"}. On both markets LEAR proved the most
accurate model and the DNN its statistical equal, indistinguishable
under the Giacomini--White test ($p>0.16$), while both significantly
outperformed the pure Transformer and all three beat the weekly-naive
baseline. This ordering inverts the rankings of the source papers, in
which the DNN edges LEAR [@lago2021] and the Transformer leads the
DNN [@llorente2025transformer]. The inversion is attributable to the
deep models' reduced tuning budget in this study rather than to any
inherent weakness of their architectures. Together, the two threads
constitute a production ML platform that ingests live market data,
recalibrates and forecasts daily, monitors prediction quality and data
drift, and maintains a complete audit trail from every forecast back to
the exact code commit and data window that produced it.

## Future work

Several extensions follow directly from the limitations discussed in
Chapter [8](#ch:discussion){reference-type="ref"
reference="ch:discussion"}.

- **Modelling fidelity.** Restore the 1456 day calibration window and
  the LARS+AIC $\lambda$-selection of the original benchmark once the
  data history is long enough. Tune the Transformer per market rather
  than reusing the paper defaults, and run it in its native train once
  and renormalise mode rather than the rolling refit used here. Run an
  `epftoolbox` side by side on the original 2016--2018 datasets to
  separate replication error from regime change.

- **Probabilistic forecasting.** Extend the point forecasts to
  predictive distributions and evaluate with pinball loss or the
  continuous ranked probability score (CRPS), the direction surveyed by
  Nowotarski and Weron [@nowotarski2018].

- **Reproducibility of stochastic models.** Demonstrate the re-run for
  the DNN and Transformer under controlled seeds with GPU non
  determinism suppressed, extending the deterministic LEAR
  demonstration.

- **Data-testing maturity.** Formalise the feature benefit, feature
  cost, and privacy analyses and add a data quality CI gate, the binding
  constraint on the ML Test Score.

- **Drift recalibration and coverage.** Recalibrate the drift detector,
  which currently flags every report, and extend forecasting and drift
  to the remaining ingested bidding zones.

- **Tooling adoption triggers.** Adopt MLflow, Kubernetes, a
  cloud-managed model store, or DVC if and when their named, observable
  triggers are reached
  (Chapter [5](#ch:system-implementation){reference-type="ref"
  reference="ch:system-implementation"}).

# Glossary {#app:glossary}

LEAR

:   Lasso Estimated AutoRegressive ensemble for day-ahead electricity
    price forecasting, the primary baseline model from Lago et
    al. [@lago2021].

DNN

:   Deep neural network. In this thesis, a multi-layer perceptron
    ensemble whose final prediction is the arithmetic mean of
    `n_dnn_ensemble` replicates trained with distinct random seeds.

EPF

:   Electricity price forecasting, the task of predicting day-ahead
    wholesale electricity prices for a given bidding zone from
    historical prices and exogenous signals.

ENTSO-E

:   European Network of Transmission System Operators for Electricity,
    the body that operates the Transparency Platform API from which the
    platform ingests price, load, and generation data.

Lasso

:   Least Absolute Shrinkage and Selection Operator, an L1-regularised
    linear regression that simultaneously shrinks coefficients and
    performs automatic feature selection.

TPE

:   Tree-structured Parzen Estimator, the Bayesian optimisation sampler
    used by Optuna when running `forecast-cli tune`.

MLOps

:   Machine Learning Operations, the set of practices for reliably
    building, deploying, and operating machine learning systems in
    production.

ReplacingMergeTree

:   A ClickHouse storage engine that deduplicates rows sharing the same
    sort key during background merge, used throughout the platform to
    make re-insertion safe under the platform's append-only write
    semantics.

Tailscale

:   A mesh VPN built on WireGuard used here to grant the GitHub Actions
    runner ephemeral SSH access to the deploy host without exposing any
    port on that host to the public internet.

Loki

:   Grafana Labs' log aggregation system, used here as the
    structured-log backend for all Prefect flows and infrastructure
    modules via direct Python push through `python-logging-loki`.

Evidently

:   An open-source library for data and model drift detection, used here
    in in-process mode inside the Prefect drift-detection flow to apply
    its `DataDriftPreset`, which auto-selects a drift test
    (Kolmogorov--Smirnov or Wasserstein, by sample size) and compares a
    90-day reference window against a 7-day current window.

# ML Test Score Worksheet {#app:mlts-worksheet}

The full per-item ML Test Score worksheet of Breck et
al. [@breck2017mltestscore] follows. Each item scores $1$ when the
capability exists and is automated, tested, or repeatable, $0.5$ when it
exists but is manual, partial, or ad-hoc, and $0$ when it is absent or
genuinely not applicable to the domain, with one line of evidence
pointing into the repository. The section sums are Data $2.5$, Model
development $3.0$, ML infrastructure $4.0$, and Monitoring $4.0$. The
final score is their minimum, $\mathbf{2.5}$
(§[7.1](#sec:res-mlts){reference-type="ref" reference="sec:res-mlts"}).

   **\#**  **Test**                                 **Score**  **Evidence**
  -------- --------------------------------------- ----------- -------------------------------------------------------------------------------------------------------------------------
     1     Feature expectations in a schema             1      `enforce_schema()` in `domain/curves.py`, raises on dtype/column mismatch, tested in `tests/domain/`
     2     All features are beneficial                  0      No systematic ablation documenting each feature's contribution (`forecast-cli ablate` exists but was not used for this)
     3     No feature costs too much                    0      No per-transformer latency/compute-cost analysis, no documented cost threshold
     4     Features meet meta-level requirements        0      No regulatory/contractual/fairness requirements apply to wholesale price data
     5     Pipeline has privacy controls                0      ENTSO-E data is public market data with no PII, n/a domain, scored 0
     6     New features added quickly                  0.5     `FeatureTransformer` ABC documented in `CONTRIBUTING.md`, manual process, no scaffold/SLA
     7     All input feature code is tested             1      `tests/.../test_transformers.py` covers every transformer, runs in CI

  : Section 1, Data tests (sum 2.5 / 7).

   **\#**  **Test**                                 **Score**  **Evidence**
  -------- --------------------------------------- ----------- --------------------------------------------------------------------------------------------------------------------
     1     Model specs reviewed and submitted          0.5     `configs/*.py` are first-class Git files under PR review, no automated spec-schema gate
     2     Offline and online metrics correlate        0.5     Reconciliation computes the same MAE/RMSE/sMAPE on live predictions as backtesting, no formal correlation study
     3     All hyperparameters tuned                   0.5     DNN tuned with 6 HPs via Optuna, LEAR $\lambda$ cross-validated, windows from the paper, Transformer partly manual
     4     Impact of model staleness known             0.5     Daily refit bounds staleness $<24$ h, no documented degradation experiment at 48 h / 7 d
     5     A simpler model is not better               0.5     LEAR vs DNN vs Transformer tracked, rMAE vs weekly-naive, not an automated gate
     6     Model quality sufficient on slices          0.5     Per-area backtests, `compute_metrics_per_hour`, no automated per-slice gate
     7     Model tested for inclusion (fairness)        0      n/a domain, no demographic groups, scored 0

  : Section 2, Model development tests (sum 3.0 / 7).

   **\#**  **Test**                            **Score**  **Evidence**
  -------- ---------------------------------- ----------- ----------------------------------------------------------------------------------------------------------------------------------
     1     Training is reproducible               0.5     `experiment_runs` carries `git_sha` + data windows + `model_artifact_id`, LEAR deterministic, GPU non-determinism not suppressed
     2     Model specs are unit tested             1      `test_models.py`, `test_transformer_model.py`, `test_dnn_ensemble.py` in CI
     3     Full pipeline integration tested        1      LEAR smoke test plus full Compose-stack smoke in `pr_smoke.yml`
     4     Quality validated before serving        0      No quality gate before predictions are written to `experiment_predictions`
     5     Debuggable by observing steps          0.5     Loki structured logging, W&B per-epoch loss, no per-layer step-through
     6     Tested via a canary process            0.5     `cd_deploy` `smoke_run` triggers a forecast post-deploy, checks completion, not quality
     7     Quick and safe rollback                0.5     Artefact blobs in `model_artifacts`, image rollback via build + restart, no automated rollback command

  : Section 3, ML infrastructure tests (sum 4.0 / 7).

   **\#**  **Test**                              **Score**  **Evidence**
  -------- ------------------------------------ ----------- ---------------------------------------------------------------------------------------------------------------------------
     1     Dependency changes notified               0      `uv.lock` tracked in Git, no Dependabot/Renovate notification
     2     Data invariants hold train & serve       0.5     `enforce_schema` at construction, shared preprocessor, not independently monitored/alerted
     3     Train/serve features compute alike        1      A single `DataPreprocessor` used by both `BacktestRunner` and `LiveRunner`, a structural guarantee
     4     Models are not too stale                 0.5     Daily refit $<24$ h, Grafana `data-staleness` alert on inputs, no dedicated model-age alert
     5     The model is numerically stable          0.5     `asinh` scaler stabilises spikes and negatives, no automated NaN/inf assertion on outputs
     6     Compute has not regressed                0.5     `training_duration_seconds` tracked per run and in W&B, no automated threshold alert
     7     Prediction quality not regressed          1      `_maybe_alert_accuracy_degradation` (MAE $>1.5\times$ 30-day median) and the `reconciliation-missed` rule, both automated

  : Section 4, Monitoring tests (sum 4.0 / 7).

A reproducible, monitored electricity-price-forecasting platform,
together with a faithful, significance-tested comparison of the
benchmark LEAR, DNN, and Transformer models on current ENTSO-E market
data.

  ---------------------------------------
  Technical
  University of
  Denmark
  Richard Petersens Plads, Building 324
  2800 Kgs. Lyngby
  Tlf. 4525 1700
  [www.dtu.dk](www.dtu.dk){.uri}
  ---------------------------------------
