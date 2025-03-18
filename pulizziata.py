# %%
from geopandas import read_file, GeoDataFrame
from pandas import concat, read_csv, NA

# %% Càrrica i dati Istat
riggiuni_italia = read_file("./Limiti01012025/Reg01012025/Reg01012025_WGS84.shp")
pruvinci_italia = read_file("./Limiti01012025/ProvCM01012025/ProvCM01012025_WGS84.shp")
cumuna_italia = read_file("./Limiti01012025/Com01012025/Com01012025_WGS84.shp")

# %% Sarba i cunfini dî riggiuni
riggiuni_sicilia = (
    riggiuni_italia[['DEN_REG', 'geometry']][riggiuni_italia['DEN_REG'] == 'Sicilia']
    .rename(columns={'DEN_REG': 'ITA'})
    .reset_index(drop=True)
)
riggiuni_sicilia['SCN'] = 'Sicilia'

riggiuni_calabbria = (
    riggiuni_italia[['DEN_REG', 'geometry']][riggiuni_italia['DEN_REG'] == 'Calabria']
    .rename(columns={'DEN_REG': 'ITA'})
    .reset_index(drop=True)
)
riggiuni_calabbria['SCN'] = 'Calabbria'

riggiuna_junciuti = GeoDataFrame(concat([riggiuni_sicilia, riggiuni_calabbria], ignore_index=True))
riggiuna_junciuti = riggiuna_junciuti[['SCN', 'ITA', 'geometry']]
riggiuna_junciuti.to_crs(epsg=4326).to_file('./riggiuna/riggiuna.shp', encoding='utf-8')

# %% Sarba i cunfini dî pruvinci
pruvinci_sicilia = (
    pruvinci_italia[['DEN_UTS', 'COD_UTS', 'geometry']][pruvinci_italia['COD_REG'] == 19]
    .rename(columns={'DEN_UTS': 'ITA', 'COD_UTS': 'PROVINCE'})
    .reset_index(drop=True)
)
noma_pruvinci_sicilia = {
    'Catania': 'Catania',
    'Messina': 'Missina',
    'Palermo': 'Palermu',
    'Agrigento': 'Girgenti',
    'Caltanissetta': 'Nissa',
    'Enna': 'Castruggiuvanni',
    'Ragusa': 'Ragusa',
    'Siracusa': 'Saragusa',
    'Trapani': 'Tràpani'
}
pruvinci_sicilia['SCN'] = pruvinci_sicilia['ITA'].map(noma_pruvinci_sicilia)

pruvinci_calabbria = (
    pruvinci_italia[['DEN_UTS', 'COD_UTS', 'geometry']]
    [(pruvinci_italia['COD_REG'] == 18) & (pruvinci_italia['DEN_UTS'] == 'Reggio di Calabria')]
    .rename(columns={'DEN_UTS': 'ITA', 'COD_UTS': 'PROVINCE'})
    .reset_index(drop=True)
)
noma_pruvinci_calabbria = {
    'Reggio di Calabria': 'Riggiu'
}
pruvinci_calabbria['SCN'] = pruvinci_calabbria['ITA'].map(noma_pruvinci_calabbria)

pruvinci_junciuti = GeoDataFrame(concat([pruvinci_sicilia, pruvinci_calabbria], ignore_index=True))
pruvinci_junciuti = pruvinci_junciuti[['SCN', 'ITA', 'PROVINCE', 'geometry']]
pruvinci_junciuti.to_crs(epsg=4326).to_file('./pruvinci/pruvinci.shp', encoding='utf-8')

# %% Sarba i cunfini dî cumuna
cumuna_sicilia = (
    cumuna_italia[['COMUNE', 'COD_UTS', 'geometry']][cumuna_italia['COD_REG'] == 19]
    .rename(columns={'COMUNE': 'ITA', 'COD_UTS': 'PROVINCE'})
    .reset_index(drop=True)
)

cumuna_siculofuni = [
    'Scilla', 'Roghudi', 'Bova', 'Bova Marina', 'Condofuri', 'Roccaforte del Greco',
    'Santo Stefano in Aspromonte', 'San Roberto', 'Fiumara', 'Campo Calabro',
    'Villa San Giovanni', 'Reggio di Calabria', 'Calanna', 'Laganadi',
    'Sant\'Alessio in Aspromonte', 'Cardeto', 'Bagaladi', 'San Lorenzo',
    'Motta San Giovanni', 'Montebello Jonico', 'Melito di Porto Salvo'
]
cumuna_calabbria = (
    cumuna_italia[['COMUNE', 'COD_UTS', 'geometry']]
    [
        (cumuna_italia['COD_REG'] == 18) &
        (cumuna_italia['COD_PROV'] == 80) &
        (cumuna_italia['COMUNE'].isin(cumuna_siculofuni))
    ]
    .rename(columns={'COMUNE': 'ITA', 'COD_UTS': 'PROVINCE'})
    .reset_index(drop=True)
)

cumuna_junciuti = GeoDataFrame(concat([cumuna_sicilia, cumuna_calabbria], ignore_index=True))

cumuna_junciuti['SCN'] = ''
cumuna_junciuti['LOCAL'] = ''
cumuna_junciuti['DEMONYM'] = ''
cumuna_junciuti['FROM'] = ''
cumuna_junciuti = cumuna_junciuti[['SCN', 'ITA', 'PROVINCE', 'LOCAL', 'DEMONYM', 'FROM', 'geometry']]

cumuna_junciuti = cumuna_junciuti.replace({'Ã¬': 'ì', 'Ã¹': 'ù', 'Ã²': 'ò', 'Ã': 'à', "\xa0": ''}, regex=True)

# %% Metti macari i noma dî cumuna 'n sicilianu
tuponimi = read_csv('./tuponimi.csv')
for index, row in tuponimi.iterrows():
    cumuna_junciuti.loc[cumuna_junciuti['ITA'] == row['ITA'], ['SCN', 'LOCAL', 'DEMONYM', 'FROM']] = [
        row['SCN'], row['LOCAL'], row['DEMONYM'], row['FROM']
    ]

cumuna_junciuti.to_crs(epsg=4326).to_file('./cumuna/cumuna.shp', encoding='utf-8')

# %% Sarba tutti tri nzèmmula
junciuti = concat([riggiuna_junciuti, pruvinci_junciuti, cumuna_junciuti]).reset_index(drop=True)
junciuti.to_crs(epsg=4326).to_file('./junciuti/junciuti.shp', encoding='utf-8')
