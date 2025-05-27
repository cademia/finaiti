# %%
from geopandas import read_file, GeoDataFrame
from pandas import concat, read_csv, NA

gpkg = "./basidati.gpkg"

# %% Càrrica i dati ISTAT
riggiuni_taliani = read_file("./Limiti01012025/Reg01012025/Reg01012025_WGS84.shp")
pruvinci_taliani = read_file("./Limiti01012025/ProvCM01012025/ProvCM01012025_WGS84.shp")
cumuna_taliani = read_file("./Limiti01012025/Com01012025/Com01012025_WGS84.shp")

# %% Riggistra i finaiti riggiunali
riggiuni_siciliana = (
    riggiuni_taliani[['DEN_REG', 'geometry']][riggiuni_taliani['DEN_REG'] == 'Sicilia']
    .rename(columns={'DEN_REG': 'ITA'})
    .reset_index(drop=True)
)
riggiuni_siciliana['SCN'] = 'Sicilia'

riggiuni_calabbrisi = (
    riggiuni_taliani[['DEN_REG', 'geometry']][riggiuni_taliani['DEN_REG'] == 'Calabria']
    .rename(columns={'DEN_REG': 'ITA'})
    .reset_index(drop=True)
)
riggiuni_calabbrisi['SCN'] = 'Calabbria'

riggiuna_junciuti = GeoDataFrame(concat([riggiuni_siciliana, riggiuni_calabbrisi], ignore_index=True))
riggiuna_junciuti = riggiuna_junciuti[['SCN', 'ITA', 'geometry']]
# riggiuna_junciuti.to_crs(epsg=4326).to_file('./riggiuna/riggiuna.shp', encoding='utf-8')
riggiuna_junciuti.to_crs(epsg=4326).to_file(gpkg, layer="riggiuna", driver="GPKG")

# %% Riggistra i finaiti pruvinciali
pruvinci_siciliani = (
    pruvinci_taliani[['DEN_UTS', 'COD_UTS', 'geometry']][pruvinci_taliani['COD_REG'] == 19]
    .rename(columns={'DEN_UTS': 'ITA'})
    .reset_index(drop=True)
)
noma_pruvinci_siciliani = {
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
pruvinci_siciliani['SCN'] = pruvinci_siciliani['ITA'].map(noma_pruvinci_siciliani)

pruvinci_calabbrisi = (
    pruvinci_taliani[['DEN_UTS', 'COD_UTS', 'geometry']]
    [(pruvinci_taliani['COD_REG'] == 18) & (pruvinci_taliani['DEN_UTS'] == 'Reggio di Calabria')]
    .rename(columns={'DEN_UTS': 'ITA'})
    .reset_index(drop=True)
)
noma_pruvinci_calabbrisi = {
    'Reggio di Calabria': 'Riggiu'
}
pruvinci_calabbrisi['SCN'] = pruvinci_calabbrisi['ITA'].map(noma_pruvinci_calabbrisi)

pruvinci_junciuti = GeoDataFrame(concat([pruvinci_siciliani, pruvinci_calabbrisi], ignore_index=True))
pruvinci_junciuti = pruvinci_junciuti[['SCN', 'ITA', 'COD_UTS', 'geometry']]
# pruvinci_junciuti.to_crs(epsg=4326).to_file('./pruvinci/pruvinci.shp', encoding='utf-8')
pruvinci_junciuti.to_crs(epsg=4326).to_file(gpkg, layer="pruvinci", driver="GPKG")

# %% Riggistra i finaiti cumunali
cumuna_siciliani = (
    cumuna_taliani[['COMUNE', 'COD_UTS', 'geometry']][cumuna_taliani['COD_REG'] == 19]
    .rename(columns={'COMUNE': 'ITA'})
    .reset_index(drop=True)
)

cumuna_siculofuni_calabbrisi = [
    'Scilla', 'Roghudi', 'Bova', 'Bova Marina', 'Condofuri', 'Roccaforte del Greco',
    'Santo Stefano in Aspromonte', 'San Roberto', 'Fiumara', 'Campo Calabro',
    'Villa San Giovanni', 'Reggio di Calabria', 'Calanna', 'Laganadi',
    'Sant\'Alessio in Aspromonte', 'Cardeto', 'Bagaladi', 'San Lorenzo',
    'Motta San Giovanni', 'Montebello Jonico', 'Melito di Porto Salvo'
]
cumuna_calabbrisi = (
    cumuna_taliani[['COMUNE', 'COD_UTS', 'geometry']]
    [
        (cumuna_taliani['COD_REG'] == 18) &
        (cumuna_taliani['COD_PROV'] == 80) &
        (cumuna_taliani['COMUNE'].isin(cumuna_siculofuni_calabbrisi))
    ]
    .rename(columns={'COMUNE': 'ITA'})
    .reset_index(drop=True)
)

cumuna_junciuti = GeoDataFrame(concat([cumuna_siciliani, cumuna_calabbrisi], ignore_index=True))

# cumuna_junciuti['SCN'] = ''
# cumuna_junciuti['LUCALI'] = ''
# cumuna_junciuti['ABBITANTI'] = ''
# cumuna_junciuti['FUNTI'] = ''
# cumuna_junciuti = cumuna_junciuti[['SCN', 'ITA', 'COD_UTS', 'LUCALI', 'ABBITANTI', 'FUNTI', 'geometry']]
cumuna_junciuti = cumuna_junciuti[['ITA', 'COD_UTS', 'geometry']]

cumuna_junciuti = cumuna_junciuti.replace({'Ã¬': 'ì', 'Ã¹': 'ù', 'Ã²': 'ò', 'Ã': 'à', "\xa0": ''}, regex=True)

# %% Junci i dati di tuponimi.csv (i noma dî cumuna 'n sicilianu, i noma di l'abbitanti, ecc.)
tuponimi = read_csv('./tuponimi.csv')
for index, row in tuponimi.iterrows():
    cumuna_junciuti.loc[cumuna_junciuti['ITA'] == row['ITA'], ['SCN', 'LUCALI', 'ABBITANTI', 'FUNTI', 'NOTI']] = [
        row['SCN'], row['LUCALI'], row['ABBITANTI'], row['FUNTI'], row['NOTI']
    ]

# cumuna_junciuti.to_crs(epsg=4326).to_file('./cumuna/cumuna.shp', encoding='utf-8')
cumuna_junciuti.to_crs(epsg=4326).to_file(gpkg, layer="cumuna", driver="GPKG")

# %% Sarba tutti cosi
# junciuti = concat([riggiuna_junciuti, pruvinci_junciuti, cumuna_junciuti]).reset_index(drop=True)
# junciuti.to_crs(epsg=4326).to_file('./junciuti/junciuti.shp', encoding='utf-8')
