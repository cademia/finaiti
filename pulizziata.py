from geopandas import read_file
from pandas import concat, read_csv

# Carrica dati ISTAT
riggiuni_italia = read_file("./Limiti01012023/Reg01012023/Reg01012023_WGS84.shp")
pruvinci_italia = read_file("./Limiti01012023/ProvCM01012023/ProvCM01012023_WGS84.shp")
cumuna_italia = read_file("./Limiti01012023/Com01012023/Com01012023_WGS84.shp")

# Sarba i cunfini dâ riggiuni_sicilia, zuè dâ Sicilia
riggiuni_sicilia = riggiuni_italia[['DEN_REG', 'geometry']][riggiuni_italia['DEN_REG'] == 'Sicilia'].rename(columns={'DEN_REG': 'ITA'}).reset_index(drop=True)
riggiuni_sicilia['SCN'] = 'Sicilia'
riggiuni_sicilia = riggiuni_sicilia[['SCN', 'ITA', 'geometry']]
riggiuni_sicilia.to_crs(epsg=4326).to_file('./riggiuni/riggiuni.shp', encoding='utf-8')

# Sarba i cunfini dî pruvinci_sicilia
pruvinci_sicilia = pruvinci_italia[['DEN_UTS', 'COD_UTS', 'geometry']][pruvinci_italia['COD_REG'] == 19].rename(columns={'DEN_UTS': 'ITA', 'COD_UTS': 'PROVINCE'}).reset_index(drop=True)
pruvinci_sicilia['SCN'] = ''
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Catania', 'SCN'] = 'Catania'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Messina', 'SCN'] = 'Missina'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Palermo', 'SCN'] = 'Palermu'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Agrigento', 'SCN'] = 'Girgenti'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Caltanissetta', 'SCN'] = 'Nissa'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Enna', 'SCN'] = 'Castruggiuvanni'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Ragusa', 'SCN'] = 'Ragusa'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Siracusa', 'SCN'] = 'Saragusa'
pruvinci_sicilia.loc[pruvinci_sicilia['ITA'] == 'Trapani', 'SCN'] = 'Tràpani'
pruvinci_sicilia = pruvinci_sicilia[['SCN', 'ITA', 'PROVINCE', 'geometry']]
pruvinci_sicilia.to_crs(epsg=4326).to_file('./pruvinci/pruvinci.shp', encoding='utf-8')

# Sarba i cunfini dî cumuna_sicilia
cumuna_sicilia = cumuna_italia[['COMUNE', 'COD_UTS', 'geometry']][cumuna_italia['COD_REG'] == 19].rename(columns={'COMUNE': 'ITA', 'COD_UTS': 'PROVINCE'}).reset_index(drop=True)
cumuna_sicilia['SCN'] = ''
cumuna_sicilia['LOCAL'] = ''
cumuna_sicilia['IPA'] = ''
cumuna_sicilia['DEMONYM'] = ''
cumuna_sicilia['FROM_CS'] = 0
cumuna_sicilia = cumuna_sicilia[['SCN', 'ITA', 'PROVINCE', 'LOCAL', 'IPA', 'DEMONYM', 'FROM_CS', 'geometry']]
cumuna_sicilia = cumuna_sicilia.replace({'Ã¬': 'ì', 'Ã¹': 'ù', 'Ã²': 'ò', 'Ã': 'à', "\xa0": ''}, regex=True)

# Metti macari i noma dî cumuna_sicilia 'n sicilianu
tupònimi = read_csv('./tuponimi.csv')
for index, row in tupònimi.iterrows():
    cumuna_sicilia.loc[cumuna_sicilia['ITA'] == row['ITA'], ['SCN', 'LOCAL', 'IPA', 'DEMONYM', 'FROM_CS']] = [row['SCN'], row['LOCAL'], row['IPA'], row['DEMONYM'], row['FROM_CS']]

cumuna_sicilia.to_crs(epsg=4326).to_file('./cumuna/cumuna.shp', encoding='utf-8')

# Sarba tutti tri nzèmmula
junciuti = concat([riggiuni_sicilia, pruvinci_sicilia, cumuna_sicilia]).reset_index(drop=True)
junciuti.to_crs(epsg=4326).to_file('./junciuti/junciuti.shp', encoding='utf-8')
