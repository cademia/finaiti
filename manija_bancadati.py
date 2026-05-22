# %% PANORAMICA - WHAT THIS SCRIPT DOES
# ================================================================
#
# manija_bancadati.py — Build script for the "Finaiti" spatial database.
#
# This script is a ONE-SHOT BUILDER. You run it once and it reads a set of
# raw ISTAT shapefiles (the official administrative boundaries of Italy) and
# turns them into a single, clean GeoPackage file: ./bancadati.gpkg
#
# That GeoPackage is the resource consumed by the Dizziunariu geography
# engine (unni.dizziunariu.com). The whole point is to keep ONLY the area we
# care about — Sicily, plus the Sicilian-speaking comuni around Reggio di
# Calabria — to attach the Sicilian-language names (SCN), and to write every
# administrative level as BOTH a polygon layer and a matching point layer.
#
# ----------------------------------------------------------------
# THE STEPS, IN ORDER (each writes one or more layers to the .gpkg):
# ----------------------------------------------------------------
#
#   1. SETUP
#        - Imports, the path to the output GeoPackage (PRICU_GPKG), and a
#          handful of lookup tables (Italian->Sicilian province names, the
#          list of Sicilian-speaking Calabrian comuni, the city codes that
#          own sub-districts, and the locality-type descriptions).
#        - Four helper functions:
#            curreggi_utf8()              -> repairs mojibake / bad encoding
#            cummerti_n_wgs84()           -> reprojects a layer to WGS84
#            cria_solu_di_punti()         -> makes a point layer from centroids
#            ncucchia_cuurdinati_ufficiali() -> attaches ISTAT's official
#                                               point coordinates by matching
#                                               on the PRO_COM code
#
#   2. RIGGIUNA (regions)        -> layer: riggiuna
#        Extracts Sicily and Calabria as region polygons.
#
#   3. PRUVINCI (provinces)      -> layer: pruvinci
#        All Sicilian provinces + Reggio di Calabria only, with Sicilian names.
#
#   4. CUMUNA (comuni/municipalities) -> layers: cumuna, cumuna_punti
#        All Sicilian comuni + the Sicilian-speaking Calabrian ones.
#        Merges tuponimi.csv to attach Sicilian names and demographic fields.
#        Builds a point layer preferring ISTAT's official coordinates,
#        falling back to polygon centroids when no official point exists.
#
#   5. CIRCUSCRIZZIONI (city districts, ASC level 1)
#        -> layers: circuscrizzioni, circuscrizzioni_punti
#        Only for the eight big cities that are divided into districts.
#
#   6. QUARTERA (quarters, ASC level 2) — PALERMO ONLY
#        -> layers: quartera_palermu, quartera_palermu_punti
#
#   7. SUTTAQUARTERA (sub-quarters, ASC level 3) — PALERMO ONLY
#        -> layers: suttaquartera_palermu, suttaquartera_palermu_punti
#
#   8. LUCALITA / FRAZZIONI (hamlets and populated places)
#        -> layers: frazzioni, frazzioni_punti,
#                   frazzioni_abbitati, frazzioni_abbitati_punti
#        Localities that are NOT the main town centre, with population,
#        household and altitude data attached.
#
#   9. SUMMARY REPORT
#        Prints every layer written to the GeoPackage with its feature count.
#
# ----------------------------------------------------------------
# KEY CONVENTIONS USED THROUGHOUT:
# ----------------------------------------------------------------
#
#   - COD_REG = 19  -> Sicily ;  COD_REG = 18 -> Calabria.
#   - 'ITA' column  = the Italian name ;  'SCN' = the Sicilian name.
#     Where we don't yet have a Sicilian translation, SCN is set equal to ITA
#     as a placeholder.
#   - Every layer is reprojected to WGS84 (EPSG:4326) before being written.
#   - Source CRS for ISTAT point coordinates is UTM zone 32N (EPSG:32632);
#     centroids are computed in EPSG:32633 to stay on a metric grid.
#
# ================================================================

# %% CÀRRICU DÎ LIBBRARÌI
# ================================================

from geopandas import read_file, GeoDataFrame  # reading shapefiles and holding spatial tables
from pandas import concat, read_csv, to_numeric, notna  # joining tables and cleaning columns
from pathlib import Path  # filesystem paths
from shapely.geometry import Point # building point geometries by hand
from pyproj import Transformer  # converting coordinates between projections (UTM > WGS84)

# %% CUNFIJURAZZIONI, CUSTANTI, FUNZIONI D'AJUTU
# ================================================

# Path to the output GeoPackage. Every layer the script builds is written
# here. If the file already exists, each layer is overwritten as it is saved.
PRICU_GPKG = "./bancadati.gpkg"

# Lookup: Italian province name -> Sicilian province name. Used to fill the
# SCN column for provinces. Reggio di Calabria is included because part of its
# territory is Sicilian-speaking.
NOMA_DI_LI_PRUVINCI_N_SICILIANU = {
    'Catania': 'Catania',
    'Messina': 'Missina',
    'Palermo': 'Palermu',
    'Agrigento': 'Girgenti',
    'Caltanissetta': 'Nissa',
    'Enna': 'Castruggiuvanni',
    'Ragusa': 'Ragusa',
    'Siracusa': 'Saragusa',
    'Trapani': 'Tràpani',
    'Reggio di Calabria': 'Riggiu'
}

# The Calabrian comuni (in the province of Reggio) that are historically
# Sicilian-speaking. Only these are pulled in from Calabria; the rest of the
# region is ignored. Used to filter comuni and their localities.
CUMUNA_SICULOFUNI_DI_LA_CALABRIA = [
    'Scilla', 'Roghudi', 'Bova', 'Bova Marina', 'Condofuri', 'Roccaforte del Greco',
    'Santo Stefano in Aspromonte', 'San Roberto', 'Fiumara', 'Campo Calabro',
    'Villa San Giovanni', 'Reggio di Calabria', 'Calanna', 'Laganadi',
    'Sant\'Alessio in Aspromonte', 'Cardeto', 'Bagaladi', 'San Lorenzo',
    'Motta San Giovanni', 'Montebello Jonico', 'Melito di Porto Salvo'
]

CODICI_DI_LI_CITA_CU_LI_QUARTERA = {
    87015: 'Catania',
    83048: 'Missina',
    82053: 'Palermu',
    89017: 'Saragusa',
    81021: 'Tràpani',
    84001: 'Girgenti',
    88009: 'Mòdica',
    80063: 'Riggiu'
}

DISCRIZZIONI_DI_LI_TIPI_DI_LUCALITA = {
    1: 'Centru abbitatu',
    2: 'Nucriu abbitatu',
    3: 'Lucalità pruduttiva',
    4: 'Casi sparsi'
}

def curreggi_utf8(df):
    """
    Curreggi l'errura d'UTF-8 ntê culonni di testu d'un DataFrame.
    """
    currizzioni = {
        # Vucali minùsculi cu l'accenti - spazziu nurmali
        'Ã ': 'à', 'Ã¨': 'è', 'Ã©': 'é', 'Ã¬': 'ì', 'Ã²': 'ò', 'Ã¹': 'ù',
        
        # Vucali minùsculi cu l'accenti - spazziu senza spartìbbili
        'Ã\xa0': 'à', 'Ã¨\xa0': 'è', 'Ã©\xa0': 'é', 'Ã¬\xa0': 'ì', 'Ã²\xa0': 'ò', 'Ã¹\xa0': 'ù',
        
        # Vucali majùsculi cu l'accenti
        'Ã\x80': 'À', 'Ã\x88': 'È', 'Ã\x89': 'É', 'Ã\x8c': 'Ì', 'Ã\x92': 'Ò', 'Ã\x99': 'Ù',
        
        # Autri caràttari
        'Ã§': 'ç',  # cedilla
        'Ã±': 'ñ',  # ñ spagnola
        'Â°': '°',  # sìmmulu dû gradu
        'â\x80\x99': "'",  # apòstrufu curbu
        'â\x80\x93': '-',  # trattinu curtu
        'â\x80\x94': '-',  # trattinu longu
        
        # Prubblemi di spazziatura
        '\xa0': ' ',  # spazziu senza spartìbbili
        '\u00a0': ' ',  # autra furma di spazziu senza spartìbbili
        '\u2009': ' ',  # spazziu finu
        '\u202f': ' ',  # spazziu strittu senza spartìbbili
    }
    return df.replace(currizzioni, regex=True)


def cummerti_n_wgs84(gdf):
    """
    Cummerti un GeoDataFrame ntô sistema di cuurdinati WGS84 (EPSG:4326).
    """
    if gdf.crs != 'EPSG:4326':
        return gdf.to_crs('EPSG:4326')
    return gdf


def cria_solu_di_punti(puliguni_gdf, crs_prujizzioni='EPSG:32633'):
    """
    Crìa un solu di punti a pàrtiri dî cintroidi dî pulìguni. Appoi i cummerti 'n WGS84.
    """
    punti = puliguni_gdf.copy()
    
    # Prujetta ntô CRS spicificatu pû càrculu pricisu dû cintroidi
    punti = punti.to_crs(crs_prujizzioni)
    punti['geometry'] = punti.geometry.centroid
    
    # Cummerti arrè 'n WGS84
    return punti.to_crs('EPSG:4326')


def ncucchia_cuurdinati_ufficiali(df_target, punti_ufficiali, campu_punti='PRO_COM', campu_target='PRO_COM'):
    """
    Ncucchia i cuurdinati ufficiali ô GeoDataFrame target.
    
    P'ogni ringu di df_target, paraggia u valuri di campu_target cu chiḍḍu di campu_punti 
    ntô dataset punti_ufficiali. S'attrova na currispunnenza, copia i cuurdinati ufficiali 
    (POINT_X, POINT_Y o geometry) e cî duna â giomitrìa dû ringu chi ci currispunni di df_target.
    """
    nummaru_ncucchiati = 0
    innici_attualizzati = []
    
    if campu_punti not in punti_ufficiali.columns:
        print(f"Accura: {campu_punti} nun s'attruvau ntrê dati di punti_ufficiali")
        return df_target, 0
    
    # Firtra pi centru principali (CENTRO_CL = 1) si cc'è
    if 'CENTRO_CL' in punti_ufficiali.columns:
        centri_principali = punti_ufficiali[punti_ufficiali['CENTRO_CL'] == 1].copy()
    else:
        centri_principali = punti_ufficiali
    
    cummirtituri = Transformer.from_crs('EPSG:32632', 'EPSG:4326')
    
    for innici, ringu in df_target.iterrows():
        if campu_target in ringu:
            valuri = int(ringu[campu_target])
        else:
            continue
        
        ringu_puntu = centri_principali[centri_principali[campu_punti] == valuri]
        
        if not ringu_puntu.empty:
            if 'POINT_X' in ringu_puntu.columns and 'POINT_Y' in ringu_puntu.columns:
                x = ringu_puntu.iloc[0]['POINT_X']
                y = ringu_puntu.iloc[0]['POINT_Y']
                luncitutini, latitutini = cummirtituri.transform(x, y)
                df_target.at[innici, 'geometry'] = Point(luncitutini, latitutini)
                nummaru_ncucchiati += 1
                innici_attualizzati.append(innici)
            elif 'geometry' in ringu_puntu.columns:
                df_target.at[innici, 'geometry'] = ringu_puntu.iloc[0]['geometry']
                nummaru_ncucchiati += 1
                innici_attualizzati.append(innici)
    
    return df_target, nummaru_ncucchiati, innici_attualizzati


# %% RIGGIUNA - Sicilia e Calàbbria (di jusu)
# ================================================

print("Càrricu i dati dî riggiuna...")

riggiuna_italia = read_file("./Limiti01012025/Reg01012025/Reg01012025_WGS84.shp")

print("Elàbburu i dati dî riggiuna...")

# Astraji a Sicilia
riggiuni_sicilia = (
    riggiuna_italia[riggiuna_italia['DEN_REG'] == 'Sicilia']
    [['DEN_REG', 'geometry']]
    .rename(columns={'DEN_REG': 'ITA'})
    .reset_index(drop=True)
)
riggiuni_sicilia['SCN'] = 'Sicilia'

# Astraji a Calàbbria
riggiuni_calabbria = (
    riggiuna_italia[riggiuna_italia['DEN_REG'] == 'Calabria']
    [['DEN_REG', 'geometry']]
    .rename(columns={'DEN_REG': 'ITA'})
    .reset_index(drop=True)
)
riggiuni_calabbria['SCN'] = 'Calabbria'

# Junci i riggiuna
riggiuna_puliguni = GeoDataFrame(concat([riggiuni_sicilia, riggiuni_calabbria], ignore_index=True))
riggiuna_puliguni = riggiuna_puliguni[['SCN', 'ITA', 'geometry']]

print("Riggistru i dati dî riggiuna...")

riggiuna_puliguni = cummerti_n_wgs84(riggiuna_puliguni)
riggiuna_puliguni.to_file(PRICU_GPKG, layer="riggiuna", driver="GPKG")


# %% PRUVINCI
# ================================================

print("\nCàrricu i dati dî pruvinci...")

pruvinci_italia = read_file("./Limiti01012025/ProvCM01012025/ProvCM01012025_WGS84.shp")

print("Elàbburu i dati dî pruvinci...")

# Astraji i pruvinci dâ Sicilia (COD_REG=19)
pruvinci_sicilia = (
    pruvinci_italia[pruvinci_italia['COD_REG'] == 19]
    [['DEN_UTS', 'COD_UTS', 'SIGLA', 'TIPO_UTS', 'geometry']]
    .rename(columns={'DEN_UTS': 'ITA'})
    .reset_index(drop=True)
)

# Mappa i noma taliani a chiḍḍi siciliani
pruvinci_sicilia['SCN'] = pruvinci_sicilia['ITA'].map(NOMA_DI_LI_PRUVINCI_N_SICILIANU)

# Astraji a pruvincia di Riggiu
pruvinci_calabbria = (
    pruvinci_italia[
        (pruvinci_italia['COD_REG'] == 18) &
        (pruvinci_italia['DEN_UTS'] == 'Reggio di Calabria')
    ]
    [['DEN_UTS', 'COD_UTS', 'SIGLA', 'TIPO_UTS', 'geometry']]
    .rename(columns={'DEN_UTS': 'ITA'})
    .reset_index(drop=True)
)
pruvinci_calabbria['SCN'] = pruvinci_calabbria['ITA'].map(NOMA_DI_LI_PRUVINCI_N_SICILIANU)

# Junci i pruvinci
pruvinci_puliguni = GeoDataFrame(concat([pruvinci_sicilia, pruvinci_calabbria], ignore_index=True))
pruvinci_puliguni = pruvinci_puliguni[['SCN', 'ITA', 'COD_UTS', 'SIGLA', 'TIPO_UTS', 'geometry']]

print("Riggistru i dati dî pruvinci...")

pruvinci_puliguni = cummerti_n_wgs84(pruvinci_puliguni)
pruvinci_puliguni.to_file(PRICU_GPKG, layer="pruvinci", driver="GPKG")


# %% CUMUNA - Pulìguni e punti
# ================================================

print("\nCàrricu i dati dî cumuna...")

cumuna_italia = read_file("./Limiti01012025/Com01012025/Com01012025_WGS84.shp")

# Càrrica i dati puntuali p'accucchiari i cuurdinati
print("Càrricu i punti di LocalitaPuntuali...")

try:
    dati_puntuali = read_file("./LocalitaPuntuali_21/Localita_2021_Point.shp")
except Exception as e:
    print(f"Accura: Nun potti carricari i dati di LocalitaPuntuali: {e}")
    dati_puntuali = None

print("Elàbburu i dati dî cumuna...")

# Astraji i cumuna siciliani
cumuna_sicilia = (
    cumuna_italia[cumuna_italia['COD_REG'] == 19]
    [['COMUNE', 'COD_UTS', 'PRO_COM_T', 'geometry']]
    .rename(columns={'COMUNE': 'ITA'})
    .reset_index(drop=True)
)

# Astraji i cumuna calabbrisi
cumuna_calabbria = (
    cumuna_italia[
        (cumuna_italia['COD_REG'] == 18) &
        (cumuna_italia['COD_UTS'] == 280) &
        (cumuna_italia['COMUNE'].isin(CUMUNA_SICULOFUNI_DI_LA_CALABRIA))
    ]
    [['COMUNE', 'COD_UTS', 'PRO_COM_T', 'geometry']]
    .rename(columns={'COMUNE': 'ITA'})
    .reset_index(drop=True)
)

# Junci i cumuna
cumuna_puliguni = GeoDataFrame(concat([cumuna_sicilia, cumuna_calabbria], ignore_index=True))

print("Abbersu i prubblemi di cudìfica...")

cumuna_puliguni = curreggi_utf8(cumuna_puliguni)

print("Junciu i dati dî tupònimi...")

tuponimi = read_csv('./tuponimi.csv')

# Junci chî dati dî tupònimi
cumuna_puliguni = cumuna_puliguni.merge(
    tuponimi[['ITA', 'SCN', 'LUCALI', 'ABBITANTI', 'FUNTI', 'NOTI']], 
    on='ITA', 
    how='left'
)

# Abbersa i culonni
cumuna_puliguni = cumuna_puliguni[[
    'SCN', 'ITA', 'COD_UTS', 'PRO_COM_T', 
    'LUCALI', 'ABBITANTI', 'FUNTI', 'NOTI', 'geometry'
]]

print("Riggistru i pulìguni dî cumuna...")

cumuna_puliguni = cummerti_n_wgs84(cumuna_puliguni)
cumuna_puliguni.to_file(PRICU_GPKG, layer="cumuna", driver="GPKG")

print("Crìu i punti dî cumuna...")

cumuna_punti = cumuna_puliguni.copy()

# Prova a ncucchiari i pulìguni chî cuurdinati dî dati puntuali. Vasinnò, càrcula i cintroidi
if dati_puntuali is not None:
    print("Ncucchiu chî cuurdinati uffiçiali...")
    
    cumuna_punti, nummaru_ncucchiati, innici_attualizzati = ncucchia_cuurdinati_ufficiali(
        cumuna_punti, 
        dati_puntuali,
        campu_punti='PRO_COM',
        campu_target='PRO_COM_T'
    )
    
    print(f"Ncucchiavi {nummaru_ncucchiati} cumuna chî cuurdinati puntuali")
    
    # Càrcula i cintroidi dî cumuna senza ncucchiati
    maschira_senza_ncucchiati = ~cumuna_punti.index.isin(innici_attualizzati)
    nummaru_senza_ncucchiati = maschira_senza_ncucchiati.sum()
    
    if nummaru_senza_ncucchiati > 0:
        print(f"Càrculu i cintroidi pi {nummaru_senza_ncucchiati} cumuna senza cuurdinati puntuali")
        
        cumuna_senza_punti = cumuna_punti[maschira_senza_ncucchiati].copy()
        cumuna_senza_punti = cria_solu_di_punti(cumuna_senza_punti)
        cumuna_punti.loc[maschira_senza_ncucchiati, 'geometry'] = cumuna_senza_punti['geometry']
else:
    print("Càrculu i cintroidi pi tutti i cumuna...")
    cumuna_punti = cria_solu_di_punti(cumuna_punti)

print("Riggistru i punti dî cumuna...")

cumuna_punti = cummerti_n_wgs84(cumuna_punti)
cumuna_punti.to_file(PRICU_GPKG, layer="cumuna_punti", driver="GPKG")


# %% QUARTERA
# ================================================

print("\nCàrricu i pulìguni dî circuscrizzioni...")

circuscrizzioni_italia = read_file("./ASC_21/ASC_Liv_1_WGS84.shp")

print("Elàbburu i pulìguni dî circuscrizzioni...")

# Astraji i circuscrizzioni dî cità dâ Sicilia
circuscrizzioni_sicilia = circuscrizzioni_italia[circuscrizzioni_italia['COD_REG'] == 19].copy()

# Astraji i circuscrizzioni di Riggiu
circuscrizzioni_calabria = circuscrizzioni_italia[
    (circuscrizzioni_italia['COD_REG'] == 18) & 
    (circuscrizzioni_italia['PRO_COM'] == 80063)  # Còdici di Riggiu
].copy()

# Junci i circuscrizzioni
circuscrizzioni_puliguni = concat([circuscrizzioni_sicilia, circuscrizzioni_calabria], ignore_index=True)

# Mappa i còdici dî cità ê noma ('n sicilianu)
circuscrizzioni_puliguni['CUMUNI'] = circuscrizzioni_puliguni['PRO_COM'].map(CODICI_DI_LI_CITA_CU_LI_QUARTERA)

# Arrinòmina i culonni
circuscrizzioni_puliguni = circuscrizzioni_puliguni.rename(columns={
    'DEN_ASC1': 'ITA',
    'COD_ASC1_T': 'COD_QUARTERI',
    'TIPO_ASC1': 'TIPU'
})

# Junci i noma siciliani (NB: cammora 'n italianu)
circuscrizzioni_puliguni['SCN'] = circuscrizzioni_puliguni['ITA']

# Curreggi l'errura di cudìfica
circuscrizzioni_puliguni = curreggi_utf8(circuscrizzioni_puliguni)

# Cummerti a WGS84
circuscrizzioni_puliguni = cummerti_n_wgs84(circuscrizzioni_puliguni)

# Scarta sulu i culonni chi nni sèrbinu
circuscrizzioni_puliguni = circuscrizzioni_puliguni[[
    'SCN', 'ITA', 'CUMUNI', 'COD_UTS', 'PRO_COM', 
    'COD_QUARTERI', 'TIPU', 'geometry'
]]

print(f"Attruvavi {len(circuscrizzioni_puliguni)} circuscrizzioni")

for codici, nomu in CODICI_DI_LI_CITA_CU_LI_QUARTERA.items():
    n = len(circuscrizzioni_puliguni[circuscrizzioni_puliguni['CUMUNI'] == nomu])
    if n > 0:
        print(f"  - {nomu}: {n}")

print("Riggistru i pulìguni dî circuscrizzioni...")

circuscrizzioni_puliguni.to_file(PRICU_GPKG, layer="circuscrizzioni", driver="GPKG")

print("Crìu i punti dî circuscrizzioni...")

circuscrizzioni_punti = cria_solu_di_punti(circuscrizzioni_puliguni)

print("Riggistru i punti dî circuscrizzioni...")

circuscrizzioni_punti.to_file(PRICU_GPKG, layer="circuscrizzioni_punti", driver="GPKG")


# %% QUARTERA - sulu Palermo
# ================================================
print("\nCàrricu i pulìguni dî quartera...")
quartera_italia = read_file("./ASC_21/ASC_Liv_2_WGS84.shp")

print("\nElàbburu i quartera di Palermu...")
# Filter for Palermo only (COD_REG=19, PRO_COM=82053)
palermo_zones = quartera_italia[
    (quartera_italia['COD_REG'] == 19) & 
    (quartera_italia['PRO_COM'] == 82053)
].copy()

if len(palermo_zones) > 0:
    # Rename columns
    palermo_zones = palermo_zones.rename(columns={
        'DEN_ASC2': 'ITA',
        'COD_ASC2_T': 'COD_SUTTAQUARTERI',
        'TIPO_ASC2': 'TIPU'
    })

    # Add metadata
    palermo_zones['SCN'] = palermo_zones['ITA']
    palermo_zones['CUMUNI'] = 'Palermu'

    # Fix encoding and ensure WGS84
    palermo_zones = curreggi_utf8(palermo_zones)
    palermo_zones = cummerti_n_wgs84(palermo_zones)

    print(f"Truvavi {len(palermo_zones)} quartera di Palermu")

    # Save polygons
    palermo_zones[['SCN', 'ITA', 'CUMUNI', 'COD_UTS', 'COD_SUTTAQUARTERI', 'TIPU', 'geometry']].to_file(
        PRICU_GPKG, 
        layer="quartera_palermu", 
        driver="GPKG"
    )

    # Create and save points
    palermo_zones_punti = cria_solu_di_punti(palermo_zones)
    palermo_zones_punti[['SCN', 'ITA', 'CUMUNI', 'COD_UTS', 'COD_SUTTAQUARTERI', 'TIPU', 'geometry']].to_file(
        PRICU_GPKG, 
        layer="quartera_palermu_punti", 
        driver="GPKG"
    )
else:
    print("Nun attruvavi quartera pi Palermu")


# %% SUTTAQUARTERA - sulu Palermo
# ================================================

print("\nCàrricu i punti dî suttaquartera...")
suttaquartera_italia = read_file("./ASC_21/ASC_Liv_3_WGS84.shp")

print("Elàbburu i suttaquartera di Palermu...")
palermo_micro = suttaquartera_italia[
    (suttaquartera_italia['COD_REG'] == 19) & 
    (suttaquartera_italia['PRO_COM'] == 82053)
].copy()

if len(palermo_micro) > 0:
    # Rename columns
    palermo_micro = palermo_micro.rename(columns={
        'DEN_ASC3': 'ITA',
        'COD_ASC3_T': 'COD_MICRUQUARTERI',
        'TIPO_ASC3': 'TIPU'
    })
    
    # Add metadata
    palermo_micro['SCN'] = palermo_micro['ITA']
    palermo_micro['CUMUNI'] = 'Palermu'
    
    # Fix encoding and ensure WGS84
    palermo_micro = curreggi_utf8(palermo_micro)
    palermo_micro = cummerti_n_wgs84(palermo_micro)
    
    print(f"Truvavi {len(palermo_micro)} suttaquartera di Palermu")
    
    # Save data
    palermo_micro[['SCN', 'ITA', 'CUMUNI', 'COD_UTS', 'COD_MICRUQUARTERI', 'TIPU', 'geometry']].to_file(
        PRICU_GPKG, 
        layer="suttaquartera_palermu", 
        driver="GPKG"
    )
    
    # Create and save points
    palermo_micro_punti = cria_solu_di_punti(palermo_micro)
    palermo_micro_punti[['SCN', 'ITA', 'CUMUNI', 'COD_UTS', 'COD_MICRUQUARTERI', 'TIPU', 'geometry']].to_file(
        PRICU_GPKG, 
        layer="suttaquartera_palermu_punti", 
        driver="GPKG"
    )
else:
    print("Nun attruvavi suttaquartera pi Palermu")


# %% LOCALITIES (LUCALITÀ/FRAZZIONI) - Hamlets and populated places
# ================================================

print("\nCàrricu i dati dî lucalità...")
lucalita_gdf = read_file("./Localita_21/Localita_2021.shp")

# Filter for Sicily
lucalita_sicilia = lucalita_gdf[lucalita_gdf['COD_REG'] == 19].copy()

# Get PRO_COM codes for Sicilian-speaking Calabrian comuni
print("Identificannu i cumuna siculofuni di Calabbria...")
sicilian_speaking_calabria_codes = []
for comune_name in CUMUNA_SICULOFUNI_DI_LA_CALABRIA:
    comune_match = cumuna_puliguni[cumuna_puliguni['ITA'] == comune_name]
    if not comune_match.empty:
        sicilian_speaking_calabria_codes.append(int(comune_match.iloc[0]['PRO_COM_T']))

# Filter Calabrian localities
lucalita_calabria = lucalita_gdf[
    lucalita_gdf['PRO_COM'].isin(sicilian_speaking_calabria_codes)
].copy()

# Combine localities
lucalita = concat([lucalita_sicilia, lucalita_calabria], ignore_index=True)

print(f"Truvavi {len(lucalita)} lucalità (Sicilia: {len(lucalita_sicilia)}, Calabbria: {len(lucalita_calabria)})")

# Convert to WGS84
lucalita = cummerti_n_wgs84(lucalita)

# Filter out main centres (CENTRO_CL=0 for hamlets/frazioni)
frazzioni = lucalita[lucalita['CENTRO_CL'] == 0].copy()

print(f"Firtravi {len(frazzioni)} frazzioni (scartannu i centri principali)")

# Rename columns
frazzioni = frazzioni.rename(columns={
    'NOME': 'ITA',
    'LOC21_ID': 'COD_FRAZZIONI',
    'TIPO_LOC': 'TIPU_FRAZZIONI',
    'POP21': 'PUPULAZZIONI',
    'FAM21': 'FAMIGGI'
})

# Add Sicilian names (for now, same as Italian)
frazzioni['SCN'] = frazzioni['ITA']

# Map locality types to descriptions
frazzioni['TIPU_DESC'] = frazzioni['TIPU_FRAZZIONI'].map(DISCRIZZIONI_DI_LI_TIPI_DI_LUCALITA)

# Add comune names
# Build mapping from PRO_COM to comune name
comune_names_map = {}
for _, row in cumuna_puliguni.iterrows():
    pro_com = int(row['PRO_COM_T'])
    comune_names_map[pro_com] = row['SCN'] if notna(row['SCN']) else row['ITA']

frazzioni['CUMUNI'] = frazzioni['PRO_COM'].map(comune_names_map)

# Fix encoding issues
frazzioni = curreggi_utf8(frazzioni)

# Clean altitude data
frazzioni['ALTITÙTINI'] = to_numeric(frazzioni['ALTITUDINE'], errors='coerce')

# Select relevant columns
frazzioni = frazzioni[[
    'SCN', 'ITA', 'CUMUNI', 'COD_UTS', 'PRO_COM', 
    'COD_FRAZZIONI', 'TIPU_FRAZZIONI', 'TIPU_DESC',
    'ALTITÙTINI', 'PUPULAZZIONI', 'FAMIGGI', 'geometry'
]]

# Save polygons
print("Sarbu i pulìguni dî lucalità...")
frazzioni.to_file(PRICU_GPKG, layer="frazzioni", driver="GPKG")

# Create points using official coordinates where available
print("Crìu i punti dî lucalità...")
frazzioni_punti = frazzioni.copy()

if dati_puntuali is not None and 'LOC21_ID' in dati_puntuali.columns:
    print("Usu i cuurdinati uffiçiali di LocalitaPuntuali pi lucalità...")
    
    # Track matched records
    innici_attualizzati = []
    cummirtituri = Transformer.from_crs('EPSG:32632', 'EPSG:4326')
    
    for idx, localita in frazzioni_punti.iterrows():
        loc_id = localita['COD_FRAZZIONI']
        punto = dati_puntuali[dati_puntuali['LOC21_ID'] == loc_id]
        
        if not punto.empty:
            if 'POINT_X' in punto.columns and 'POINT_Y' in punto.columns:
                x = punto.iloc[0]['POINT_X']
                y = punto.iloc[0]['POINT_Y']
                # Convert from UTM to WGS84
                lon, lat = cummirtituri.transform(x, y)
                frazzioni_punti.at[idx, 'geometry'] = Point(lon, lat)
                innici_attualizzati.append(idx)
            elif 'geometry' in punto.columns:
                frazzioni_punti.at[idx, 'geometry'] = punto.iloc[0]['geometry']
                innici_attualizzati.append(idx)
    
    nummaru_ncucchiati = len(innici_attualizzati)
    print(f"Abbinai {nummaru_ncucchiati} lucalità chî cuurdinati uffiçiali")
    
    # Calculate centroids for unmatched localities
    maschira_senza_ncucchiati = ~frazzioni_punti.index.isin(innici_attualizzati)
    nummaru_senza_ncucchiati = maschira_senza_ncucchiati.sum()
    
    if nummaru_senza_ncucchiati > 0:
        print(f"Càlculu i centroidi pi {nummaru_senza_ncucchiati} lucalità senza cuurdinati")
        cumuna_senza_punti = frazzioni_punti[maschira_senza_ncucchiati].copy()
        cumuna_senza_punti = cria_solu_di_punti(cumuna_senza_punti)
        frazzioni_punti.loc[maschira_senza_ncucchiati, 'geometry'] = cumuna_senza_punti['geometry']
else:
    print("Càlculu i centroidi pi tutti i lucalità...")
    frazzioni_punti = cria_solu_di_punti(frazzioni_punti)

print("Sarbu i punti dî lucalità...")
frazzioni_punti.to_file(PRICU_GPKG, layer="frazzioni_punti", driver="GPKG")

# Create filtered version with only populated places
frazzioni_abbitati = frazzioni[
    (frazzioni['PUPULAZZIONI'] > 0) & 
    (frazzioni['TIPU_FRAZZIONI'].isin([1, 2]))  # Centri and nuclei abitati
].copy()

print(f"\nAnchi sarbai {len(frazzioni_abbitati)} lucalità abbitati (cu pupulazzioni > 0)")
frazzioni_abbitati.to_file(PRICU_GPKG, layer="frazzioni_abbitati", driver="GPKG")

# Points version of populated places
frazzioni_abbitati_punti = frazzioni_punti[
    (frazzioni_punti['PUPULAZZIONI'] > 0) & 
    (frazzioni_punti['TIPU_FRAZZIONI'].isin([1, 2]))
].copy()
frazzioni_abbitati_punti.to_file(PRICU_GPKG, layer="frazzioni_abbitati_punti", driver="GPKG")


# %% SUMMARY REPORT
# ================================================
print("\n" + "="*50)
print("RIASSUNTU - SUMMARY")
print("="*50)
print(f"Basi dati criata: {PRICU_GPKG}")
print("\nLiveddi cu pulìguni e punti:")
print("  - riggiuna (sulu pulìguni)")
print("  - pruvinci (sulu pulìguni)")
print("  - cumuna + cumuna_punti")
print("  - circuscrizzioni + circuscrizzioni_punti")
print("  - quartera_palermu + quartera_palermu_punti")
print("  - suttaquartera_palermu + suttaquartera_palermu_punti")
print("  - lucalita + frazzioni_punti")
print("  - frazzioni_abbitati + frazzioni_abbitati_punti")

# Verify all layers and provide statistics
print("\n" + "-"*50)
print("STATISTICHI - STATISTICS")
print("-"*50)

try:
    import fiona
    layers = fiona.listlayers(PRICU_GPKG)
    print(f"Tutali liveddi ntô GeoPackage: {len(layers)}")
    
    # Print record counts for each layer
    print("\nNùmmaru di finaiti pi liveddu:")
    for layer in sorted(layers):
        with fiona.open(PRICU_GPKG, layer=layer) as src:
            print(f"  - {layer}: {len(src)} finaiti")
            
except Exception as e:
    print(f"Could not read layer statistics: {e}")

print("\nElabburazzioni finuta!")
