"""Painel interativo de indicadores do Banco Central do Brasil."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MONTHLY_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "monthly.parquet"
INDICATORS = {
    "Meta Selic (% a.a.)": ("selic_pct_annual", "% a.a.", "percent"),
    "IPCA mensal (%)": ("ipca_pct_monthly", "%", "percent"),
    "IPCA acumulado em 12 meses (%)": ("ipca_12m_pct", "%", "percent"),
    "Dólar venda (R$/US$)": ("usd_brl_sell_avg", "R$/US$", "currency"),
}


@st.cache_data(show_spinner="Carregando os indicadores...")
def load_monthly_data(path: str) -> pd.DataFrame:
    """Read processed monthly Parquet only; this function never calls the API."""
    frame = pd.read_parquet(path)
    if "month" not in frame.columns:
        raise ValueError("O arquivo mensal precisa ter a coluna 'month'.")
    frame["month"] = pd.to_datetime(frame["month"], errors="coerce")
    if frame["month"].isna().any():
        raise ValueError("O arquivo mensal contém datas inválidas.")
    return frame.sort_values("month").reset_index(drop=True)


def _format_value(value: float, kind: str) -> str:
    if kind == "currency":
        formatted = f"{value:,.2f}"
        formatted = formatted.replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R$ {formatted}"
    return f"{value:.2f}%"


def _selected_dates(
    value: date | tuple[date, ...], start: date, end: date
) -> tuple[date, date]:
    if isinstance(value, tuple):
        if len(value) == 2:
            return value[0], value[1]
        if len(value) == 1:
            return value[0], value[0]
    elif isinstance(value, date):
        return value, value
    return start, end


def main() -> None:
    st.set_page_config(
        page_title="Indicadores Econômicos do Brasil",
        page_icon="📊",
        layout="wide",
    )
    st.title("Indicadores Econômicos do Brasil")
    st.caption(
        "Séries do Sistema Gerenciador de Séries Temporais (SGS) "
        "do Banco Central do Brasil."
    )

    if not MONTHLY_DATA_PATH.exists():
        st.error(
            "Dados processados não encontrados. Execute "
            "`python -m bcb_pipeline.cli run` na pasta do projeto e "
            "recarregue a página."
        )
        st.stop()

    if st.sidebar.button("Recarregar dados"):
        load_monthly_data.clear()
    try:
        monthly = load_monthly_data(str(MONTHLY_DATA_PATH))
    except (OSError, ValueError) as error:
        st.error(f"Não foi possível ler os dados processados: {error}")
        st.stop()

    if monthly.empty:
        st.warning("Ainda não há dados mensais disponíveis.")
        st.stop()

    first_month = monthly["month"].min().date()
    last_month = monthly["month"].max().date()
    st.sidebar.header("Filtros")
    selected_labels = st.sidebar.multiselect(
        "Indicadores", options=list(INDICATORS), default=list(INDICATORS)
    )
    period_value = st.sidebar.date_input(
        "Período",
        value=(first_month, last_month),
        min_value=first_month,
        max_value=last_month,
        format="DD/MM/YYYY",
    )
    start_date, end_date = _selected_dates(period_value, first_month, last_month)

    if not selected_labels:
        st.info("Selecione ao menos um indicador no painel de filtros.")
        st.stop()

    selected_columns = [INDICATORS[label][0] for label in selected_labels]
    filtered = monthly.loc[
        monthly["month"].dt.date.between(start_date, end_date),
        ["month", *selected_columns],
    ].copy()
    if filtered.empty:
        st.warning("Não há observações no período escolhido.")
        st.stop()

    st.subheader("Indicadores mais recentes no período")
    metric_columns = st.columns(len(selected_labels))
    for column, label in zip(metric_columns, selected_labels, strict=True):
        value_column, _, kind = INDICATORS[label]
        latest = filtered.iloc[-1]
        column.metric(label, _format_value(latest[value_column], kind))
        column.caption(f"Referência: {latest['month']:%m/%Y}")

    st.subheader("Evolução no período")
    for label in selected_labels:
        value_column, unit, _ = INDICATORS[label]
        figure = px.line(
            filtered,
            x="month",
            y=value_column,
            markers=True,
            title=label,
            labels={"month": "Mês", value_column: unit},
            template="plotly_white",
        )
        figure.update_layout(margin={"l": 16, "r": 16, "t": 55, "b": 16})
        figure.update_xaxes(tickformat="%b %Y")
        figure.update_yaxes(title_text=unit)
        st.plotly_chart(figure, use_container_width=True)

    st.subheader("Tabela de dados")
    table_labels = {"month": "Mês"}
    table_labels.update({details[0]: label for label, details in INDICATORS.items()})
    display_table = filtered.sort_values("month", ascending=False).rename(
        columns=table_labels
    )
    st.dataframe(display_table, use_container_width=True, hide_index=True)
    st.download_button(
        "Baixar tabela em CSV",
        data=display_table.to_csv(index=False).encode("utf-8-sig"),
        file_name="indicadores_bcb.csv",
        mime="text/csv",
    )
    st.caption(
        f"Dados mensais disponíveis de {first_month:%m/%Y} a {last_month:%m/%Y}. "
        "Fonte: Banco Central do Brasil (SGS)."
    )


if __name__ == "__main__":
    main()
