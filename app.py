"""
Dashboard Interativo PRODES - Desmatamento na Amazônia Legal
Autor: Lucas
Data: Novembro 2025
Descrição: Dashboard em Streamlit para visualização de dados geoespaciais do PRODES
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import os
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Dashboard PRODES",
    layout="wide",
    initial_sidebar_state="expanded"
)

# URL dos dados e caminho local
DATA_URL = "https://terrabrasilis.dpi.inpe.br/download/dataset/legal-amz-prodes/vector/yearly_deforestation.zip"
LOCAL_PARQUET = "yearly_deforestation_light.parquet"

@st.cache_data
def load_data():
    """
    Carrega e processa os dados do PRODES a partir do Shapefile.
    O decorator @st.cache_data garante que os dados sejam carregados apenas uma vez.
    Verifica se o arquivo existe localmente antes de fazer download.
    """
    try:
        # Verifica se o arquivo ZIP existe localmente
        gdf = None
        if os.path.exists(LOCAL_PARQUET):
            gdf = gpd.read_parquet(LOCAL_PARQUET)
        else:
            gdf = gpd.read_file(DATA_URL)
        
        
        
        # Mapeia as colunas do PRODES para nomes padronizados
        column_mapping = {
            'year': 'ano',
            'area_km': 'area_km2',
            'state': 'uf',
            'class_name': 'classe',
            'main_class': 'classe_principal',
            'image_date': 'data_imagem',
            'satellite': 'satelite',
            'sensor': 'sensor',
            'path_row': 'path_row',
            'uuid': 'uuid',
            'uid': 'uid'
        }
        
        # Renomeia as colunas que existem no dataset
        existing_mappings = {k: v for k, v in column_mapping.items() if k in gdf.columns}
        gdf = gdf.rename(columns=existing_mappings)
        
        # Garante que ano seja numérico
        if 'ano' in gdf.columns:
            gdf['ano'] = pd.to_numeric(gdf['ano'], errors='coerce')
            gdf = gdf.dropna(subset=['ano'])
            gdf['ano'] = gdf['ano'].astype(int)
        else:
            st.error("❌ Coluna 'year' não encontrada no dataset!")
            return None
        
        # Garante que area_km2 seja numérico
        if 'area_km2' in gdf.columns:
            gdf['area_km2'] = pd.to_numeric(gdf['area_km2'], errors='coerce')
            gdf = gdf[gdf['area_km2'] > 0]
        else:
            st.error("❌ Coluna 'area_km' não encontrada no dataset!")
            return None
        
        # Para o gráfico de municípios, vamos criar uma agregação por path_row
        # que representa cenas do satélite (proxy para localização)
        if 'path_row' in gdf.columns:
            gdf['municipio'] = gdf['path_row']  # Usando path_row como proxy
        else:
            gdf['municipio'] = gdf['uf']  # Fallback para estado
        
        # Converte para WGS84 para visualização no mapa
        if gdf.crs and gdf.crs != 'EPSG:4326':
            gdf = gdf.to_crs(epsg=4326)
        
        return gdf
        
    except Exception as e:
        st.error(f"❌ Erro ao carregar dados: {str(e)}")
        return None


def create_choropleth_map(gdf_filtered):
    """
    Cria um mapa 3D interativo usando PyDeck com extrusão.
    """
    # Limita o número de polígonos para melhor performance (máximo 10000)
    if len(gdf_filtered) > 10000:
        st.warning(f"⚠️ Exibindo amostra de 10000 Áreas de {len(gdf_filtered):,} totais para melhor performance.")
        gdf_sample = gdf_filtered.nlargest(10000, 'area_km2')
    else:
        gdf_sample = gdf_filtered
    
    # Converte para GeoJSON
    gdf_sample = gdf_sample.copy()
    
    # Normaliza os valores de área para cores (0-255) e altura
    area_min = gdf_sample['area_km2'].min()
    area_max = gdf_sample['area_km2'].max()
    
    if area_max > area_min:
        # Normaliza de 0 a 255 para cores
        gdf_sample['color_intensity'] = ((gdf_sample['area_km2'] - area_min) / (area_max - area_min) * 255).astype(int)
        # Normaliza a altura de extrusão (escala logarítmica para melhor visualização)
        gdf_sample['elevation'] = ((gdf_sample['area_km2'] - area_min) / (area_max - area_min) * 50000).astype(int) + 5000
    else:
        gdf_sample['color_intensity'] = 128
        gdf_sample['elevation'] = 10000
    
    # Cria cores RGB para cada polígono (gradiente de vermelho para amarelo)
    gdf_sample['color'] = gdf_sample['color_intensity'].apply(
        lambda x: [255, int(255 - x * 0.5), 0, 200]  # Vermelho para laranja/amarelo
    )
    
    # Calcula o centro do mapa
    center_lat = gdf_sample.geometry.centroid.y.mean()
    center_lon = gdf_sample.geometry.centroid.x.mean()
    
    # Cria a camada de polígonos 3D
    layer = pdk.Layer(
        'GeoJsonLayer',
        gdf_sample,
        opacity=0.8,
        stroked=True,
        filled=True,
        extruded=True,  # Ativa a extrusão 3D
        wireframe=True,
        get_fill_color='color',
        get_line_color=[255, 255, 255, 150],
        get_line_width=20,  # Aumenta a espessura das linhas para polígonos pequenos serem visíveis
        line_width_min_pixels=1,
        get_elevation='elevation',  # Define a altura baseada na área
        elevation_scale=1,
        pickable=True,
        auto_highlight=True
    )
    
    # Configuração da visualização 3D
    view_state = pdk.ViewState(
        latitude=center_lat,
        longitude=center_lon,
        zoom=5,
        pitch=45,  # Ângulo de visão 3D
        bearing=0
    )
    
    # Tooltip para exibir informações ao passar o mouse
    tooltip = {
        "html": "<b>Área:</b> {area_km2:.2f} km²<br/>"
                "<b>Ano:</b> {ano}<br/>"
                + ("<b>Estado:</b> {uf}<br/>" if 'uf' in gdf_sample.columns else ""),
        "style": {
            "backgroundColor": "steelblue",
            "color": "white",
            "fontSize": "14px",
            "padding": "10px"
        }
    }
    
    # Cria o deck
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style='mapbox://styles/mapbox/dark-v10'  # Mapa escuro para melhor contraste 3D
    )
    
    return deck


def main():
    """
    Função principal do dashboard.
    """
    # Título principal
    st.title("🌳 Dashboard do Desmatamento - PRODES")
    st.markdown("**Análise do desmatamento na Amazônia Legal - Dados PRODES/INPE**")
    st.markdown("_Áreas desmatadas a partir de 2008, discretizadas por ano (> 6,25 hectares)_")
    
    # Carrega os dados
    with st.spinner("🔄 Carregando dados do PRODES..."):
        gdf = load_data()
    
    if gdf is None or gdf.empty:
        st.error("❌ Não foi possível carregar os dados. Verifique a conexão e tente novamente.")
        return
    
    # Barra lateral - Filtros
    st.sidebar.header("🔍 Filtros")
    
    # Filtro 1: Slider de Ano
    if 'ano' in gdf.columns:
        ano_min = int(gdf['ano'].min())
        ano_max = int(gdf['ano'].max())
        
        ano_selecionado = st.sidebar.slider(
            "📅 Selecione o Ano",
            min_value=ano_min,
            max_value=ano_max,
            value=ano_max,
            step=1,
            help="Filtra os dados de desmatamento para o ano selecionado"
        )
    else:
        st.sidebar.error("❌ Coluna 'ano' não encontrada nos dados")
        ano_selecionado = None
    
    # Filtro 2: Multiseleção de Estado (UF)
    if 'uf' in gdf.columns:
        estados_disponiveis = sorted(gdf['uf'].unique().tolist())
        estados_selecionados = st.sidebar.multiselect(
            "🗺️ Selecione os Estados",
            options=estados_disponiveis,
            default=None,
            help="Filtra os dados por estado da Amazônia Legal"
        )
    else:
        st.sidebar.error("❌ Coluna 'uf' não encontrada nos dados")
        estados_selecionados = None
    
    # Informações sobre os dados
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Informações dos Dados")
    st.sidebar.info(f"**Total de registros:** {len(gdf):,}")
    if 'ano' in gdf.columns:
        st.sidebar.info(f"**Período:** {ano_min} - {ano_max}")
    if 'uf' in gdf.columns:
        st.sidebar.info(f"**Estados:** {gdf['uf'].nunique()}")
    
    # Aplica os filtros
    gdf_filtered = gdf.copy()
    
    if ano_selecionado and 'ano' in gdf.columns:
        gdf_filtered = gdf_filtered[gdf_filtered['ano'] == ano_selecionado]
    
    if estados_selecionados and 'uf' in gdf.columns:
        gdf_filtered = gdf_filtered[gdf_filtered['uf'].isin(estados_selecionados)]
    
    # Verifica se há dados após filtro
    if gdf_filtered.empty:
        st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados.")
        return
    
    # Layout principal - Métricas
    st.markdown("---")
    st.subheader("📈 Indicadores Principais")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        # Gráfico 1: KPI - Total Desmatado
        total_desmatado = gdf_filtered['area_km2'].sum()
        st.metric(
            label="🌲 Área Desmatada (km²)",
            value=f"{total_desmatado:,.2f}",
            delta=None,
            help=f"Área total desmatada em {ano_selecionado} nos estados selecionados"
        )
    
    with col2:
        num_poligonos = len(gdf_filtered)
        st.metric(
            label="📐 Número de Polígonos",
            value=f"{num_poligonos:,}",
            help="Quantidade de áreas de desmatamento detectadas"
        )
    
    with col3:
        area_media = gdf_filtered['area_km2'].mean()
        st.metric(
            label="📏 Área Média (km²)",
            value=f"{area_media:.2f}",
            help="Tamanho médio das áreas desmatadas"
        )
    
    with col4:
        if 'uf' in gdf_filtered.columns:
            num_estados = gdf_filtered['uf'].nunique()
            st.metric(
                label="🗺️ Estados Afetados",
                value=f"{num_estados}",
                help="Número de estados com desmatamento detectado"
            )
    
    st.markdown("---")
    
    # Gráfico 2: Mapa Coroplético
    st.subheader("🗺️ Mapa de Desmatamento")
    st.markdown(f"*Visualizando desmatamento em {ano_selecionado} - Polígonos coloridos por área*")
    
    try:
        fig_mapa = create_choropleth_map(gdf_filtered)
        st.pydeck_chart(fig_mapa, use_container_width=True)
    except Exception as e:
        st.error(f"❌ Erro ao criar mapa: {str(e)}")
        st.info("💡 Dica: O mapa pode ter problemas com muitos polígonos. Tente filtrar por ano específico.")
    
    st.markdown("---")
    
    # Layout com duas colunas para os próximos gráficos
    col_left, col_right = st.columns(2)
    
    with col_left:
        # Gráfico 3: Histograma - Distribuição do Tamanho das Áreas Desmatadas
        st.subheader("📊 Distribuição do Tamanho das Áreas Desmatadas")
        st.markdown(f"*Frequência de áreas por tamanho em {ano_selecionado}*")
        
        # Cria faixas de tamanho para melhor visualização
        df_hist = gdf_filtered.copy()
        
        # Define os bins (intervalos) para o histograma
        fig_histograma = px.histogram(
            df_hist,
            x='area_km2',
            nbins=30,
            labels={'area_km2': 'Tamanho da Área (km²)', 'count': 'Frequência'},
            color_discrete_sequence=['#e74c3c'],
            title=''
        )
        
        fig_histograma.update_traces(
            marker_line_color='white',
            marker_line_width=1.5,
            hovertemplate='<b>Tamanho: %{x:.2f} km²</b><br>Frequência: %{y}<extra></extra>'
        )
        
        fig_histograma.update_layout(
            height=500,
            xaxis_title="Tamanho da Área Desmatada (km²)",
            yaxis_title="Número de Ocorrências",
            showlegend=False,
            bargap=0.1
        )
        
        st.plotly_chart(fig_histograma, use_container_width=True)
        
        # Adiciona estatísticas descritivas
        col_stat1, col_stat2 = st.columns(2)
        with col_stat1:
            mediana = df_hist['area_km2'].median()
            st.info(f"📏 **Mediana:** {mediana:.2f} km²")
        with col_stat2:
            maior_area = df_hist['area_km2'].max()
            st.info(f"🔝 **Maior área:** {maior_area:.2f} km²")
    
    with col_right:
        # Gráfico 4: Pizza - Distribuição do Desmatamento por Estado
        st.subheader("🍰 Distribuição do Desmatamento por Estado")
        st.markdown(f"*Proporção do desmatamento em {ano_selecionado}*")
        
        if 'uf' in gdf_filtered.columns:
            desmatamento_por_uf = (
                gdf_filtered.groupby('uf')['area_km2']
                .sum()
                .reset_index()
                .sort_values('area_km2', ascending=False)
            )
            
            fig_pizza = px.pie(
                desmatamento_por_uf,
                values='area_km2',
                names='uf',
                color_discrete_sequence=px.colors.sequential.RdBu_r,
                hover_data={'area_km2': ':.2f'}
            )
            
            fig_pizza.update_traces(
                textposition='inside',
                textinfo='percent+label',
                hovertemplate='<b>%{label}</b><br>Área: %{value:.2f} km²<br>Percentual: %{percent}'
            )
            
            fig_pizza.update_layout(
                height=500,
                showlegend=True
            )
            
            st.plotly_chart(fig_pizza, use_container_width=True)
        else:
            st.info("📊 Dados de estado não disponíveis para este filtro.")
    
    st.markdown("---")
    
    # Gráfico 5: Linha - Evolução Temporal (usa dados originais, não filtrados)
    st.subheader("📊 Evolução Temporal do Desmatamento")
    st.markdown("*Série histórica completa - Tendência de desmatamento ao longo dos anos*")
    
    if 'ano' in gdf.columns:
        # Usa o DataFrame original para mostrar toda a série histórica
        evolucao_temporal = (
            gdf.groupby('ano')['area_km2']
            .sum()
            .reset_index()
            .sort_values('ano')
        )
        
        fig_linha = px.line(
            evolucao_temporal,
            x='ano',
            y='area_km2',
            markers=True,
            labels={'ano': 'Ano', 'area_km2': 'Área Desmatada (km²)'},
            color_discrete_sequence=['#d62728']
        )
        
        fig_linha.update_traces(
            line=dict(width=3),
            marker=dict(size=10),
            hovertemplate='<b>Ano: %{x}</b><br>Área: %{y:.2f} km²<extra></extra>'
        )
        
        fig_linha.update_layout(
            height=400,
            hovermode='x unified',
            xaxis_title="Ano",
            yaxis_title="Área Desmatada (km²)",
            xaxis=dict(
                tickmode='linear',
                tick0=evolucao_temporal['ano'].min(),
                dtick=1
            )
        )
        
        # Adiciona uma linha vertical para indicar o ano selecionado
        if ano_selecionado:
            fig_linha.add_vline(
                x=ano_selecionado,
                line_dash="dash",
                line_color="blue",
                line_width=2,
                annotation_text=f"📍 Ano Selecionado: {ano_selecionado}",
                annotation_position="top"
            )
        
        st.plotly_chart(fig_linha, use_container_width=True)
        
        # Estatísticas adicionais
        col_stats1, col_stats2, col_stats3 = st.columns(3)
        with col_stats1:
            ano_maior = evolucao_temporal.loc[evolucao_temporal['area_km2'].idxmax(), 'ano']
            st.info(f"📈 **Ano com maior desmatamento:** {int(ano_maior)}")
        with col_stats2:
            ano_menor = evolucao_temporal.loc[evolucao_temporal['area_km2'].idxmin(), 'ano']
            st.info(f"📉 **Ano com menor desmatamento:** {int(ano_menor)}")
        with col_stats3:
            total_historico = evolucao_temporal['area_km2'].sum()
            st.info(f"🌍 **Total acumulado:** {total_historico:,.2f} km²")
    else:
        st.info("📊 Dados temporais não disponíveis.")
    
    st.markdown("---")
    
    # Gráfico 6: Barras Empilhadas - Evolução por Estado
    st.subheader("📊 Evolução do Desmatamento por Estado ao Longo dos Anos")
    st.markdown("*Contribuição de cada estado para o desmatamento total - Série histórica*")
    
    if 'ano' in gdf.columns and 'uf' in gdf.columns:
        # Filtra por estados selecionados
        gdf_para_evolucao = gdf.copy()
        if estados_selecionados and 'uf' in gdf.columns:
            gdf_para_evolucao = gdf_para_evolucao[gdf_para_evolucao['uf'].isin(estados_selecionados)]
        
        # Agrupa por ano e estado
        evolucao_por_estado = (
            gdf_para_evolucao.groupby(['ano', 'uf'])['area_km2']
            .sum()
            .reset_index()
            .sort_values(['ano', 'area_km2'], ascending=[True, False])
        )
        
        # Cria gráfico de barras empilhadas
        fig_barras_empilhadas = px.bar(
            evolucao_por_estado,
            x='ano',
            y='area_km2',
            color='uf',
            labels={'ano': 'Ano', 'area_km2': 'Área Desmatada (km²)', 'uf': 'Estado'},
            color_discrete_sequence=px.colors.qualitative.Set3,
            barmode='stack'
        )
        
        fig_barras_empilhadas.update_traces(
            hovertemplate='<b>%{fullData.name}</b><br>Ano: %{x}<br>Área: %{y:.2f} km²<extra></extra>'
        )
        
        fig_barras_empilhadas.update_layout(
            height=500,
            xaxis_title="Ano",
            yaxis_title="Área Desmatada (km²)",
            legend_title="Estado",
            hovermode='x unified',
            xaxis=dict(
                tickmode='linear',
                tick0=evolucao_por_estado['ano'].min(),
                dtick=1
            )
        )
        
        st.plotly_chart(fig_barras_empilhadas, use_container_width=True)
        
        # Adiciona análise complementar (baseada nos estados filtrados)
        col_analise1, col_analise2, col_analise3 = st.columns(3)
        with col_analise1:
            estado_mais_desmatado = (
                gdf_para_evolucao.groupby('uf')['area_km2']
                .sum()
                .idxmax()
            )
            st.info(f"🏆 **Estado com maior desmatamento total:** {estado_mais_desmatado}")
        with col_analise2:
            ano_pico_geral = (
                gdf_para_evolucao.groupby('ano')['area_km2']
                .sum()
                .idxmax()
            )
            st.info(f"⚠️ **Ano pico de desmatamento:** {int(ano_pico_geral)}")
        with col_analise3:
            media_anual = gdf_para_evolucao.groupby('ano')['area_km2'].sum().mean()
            st.info(f"📊 **Média anual:** {media_anual:,.2f} km²")
    else:
        st.info("📊 Dados não disponíveis para este gráfico.")
    
    
    st.markdown("---")
    st.markdown("""
    **Fonte dos dados:** PRODES - Programa de Monitoramento da Floresta Amazônica Brasileira por Satélite (INPE)  
    **URL Base de Dados:** [TerraBrasilis](https://terrabrasilis.dpi.inpe.br/geonetwork/srv/eng/catalog.search#/metadata/a5220c18-f7fa-4e3e-b39b-feeb3ccc4830)  
    """)


if __name__ == "__main__":
    main()
