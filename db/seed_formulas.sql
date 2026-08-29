-- =====================================================================
-- SEED: fórmulas iniciales de atributos por posición (formula_version = 1)
-- =====================================================================
-- Pesos orientativos para arrancar la v1. Son ajustables sin tocar
-- código — basta con hacer UPDATE/INSERT en estas tablas (o subir
-- formula_version para versionar el cambio).
--
-- Simplificación v1: se agrupan posiciones en 4 familias
-- (GK, defensas, centrocampistas, delanteros) reutilizando la misma
-- fórmula dentro de cada familia. Se puede afinar por posición
-- específica (CB vs LB, por ejemplo) más adelante.
-- =====================================================================

-- Requiere que exista al menos 1 fila en data_sources y attributes_catalog
-- (ya insertadas en schema.sql).

DO $$
DECLARE
    v_ritmo   SMALLINT := (SELECT id FROM attributes_catalog WHERE code = 'ritmo');
    v_tiro    SMALLINT := (SELECT id FROM attributes_catalog WHERE code = 'tiro');
    v_pase    SMALLINT := (SELECT id FROM attributes_catalog WHERE code = 'pase');
    v_regate  SMALLINT := (SELECT id FROM attributes_catalog WHERE code = 'regate');
    v_defensa SMALLINT := (SELECT id FROM attributes_catalog WHERE code = 'defensa');
    v_fisico  SMALLINT := (SELECT id FROM attributes_catalog WHERE code = 'fisico');
BEGIN

    -- =================================================================
    -- DELANTEROS (ST, CF, LW, RW)
    -- =================================================================
    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight) VALUES
        ('ST', v_ritmo,   'successfulDribblesPercentage', 0.4),
        ('ST', v_ritmo,   'totalDuelsWonPercentage',        0.6),
        ('ST', v_tiro,    'expectedGoals',                   0.5),
        ('ST', v_tiro,    'totalShots',                      0.2),
        ('ST', v_tiro,    'shotsOnTarget',                    0.3),
        ('ST', v_pase,    'accuratePassesPercentage',          0.5),
        ('ST', v_pase,    'keyPasses',                          0.5),
        ('ST', v_regate,  'successfulDribbles',                 0.5),
        ('ST', v_regate,  'successfulDribblesPercentage',        0.5),
        ('ST', v_defensa, 'tackles',                              0.5),
        ('ST', v_defensa, 'interceptions',                         0.5),
        ('ST', v_fisico,  'aerialDuelsWonPercentage',               0.5),
        ('ST', v_fisico,  'groundDuelsWonPercentage',                0.5);

    -- Copiar la misma fórmula para CF, LW, RW (delanteros/extremos)
    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight)
    SELECT unnest(ARRAY['CF','LW','RW']::player_position[]), attribute_id, stat_field, weight
    FROM position_attribute_weights WHERE position = 'ST';

    -- =================================================================
    -- CENTROCAMPISTAS (CM, CDM, CAM, LM, RM)
    -- =================================================================
    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight) VALUES
        ('CM', v_ritmo,   'successfulDribblesPercentage', 0.5),
        ('CM', v_ritmo,   'totalDuelsWonPercentage',        0.5),
        ('CM', v_tiro,    'expectedGoals',                   0.5),
        ('CM', v_tiro,    'totalShots',                      0.5),
        ('CM', v_pase,    'accuratePassesPercentage',         0.4),
        ('CM', v_pase,    'keyPasses',                         0.3),
        ('CM', v_pase,    'accurateFinalThirdPasses',           0.3),
        ('CM', v_regate,  'successfulDribbles',                 0.5),
        ('CM', v_regate,  'successfulDribblesPercentage',        0.5),
        ('CM', v_defensa, 'tackles',                              0.4),
        ('CM', v_defensa, 'interceptions',                         0.4),
        ('CM', v_defensa, 'totalDuelsWonPercentage',                0.2),
        ('CM', v_fisico,  'aerialDuelsWonPercentage',                0.5),
        ('CM', v_fisico,  'groundDuelsWonPercentage',                 0.5);

    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight)
    SELECT unnest(ARRAY['CDM','CAM','LM','RM']::player_position[]), attribute_id, stat_field, weight
    FROM position_attribute_weights WHERE position = 'CM';

    -- =================================================================
    -- DEFENSAS (CB, LB, RB, LWB, RWB)
    -- =================================================================
    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight) VALUES
        ('CB', v_ritmo,   'groundDuelsWonPercentage',      0.5),
        ('CB', v_ritmo,   'totalDuelsWonPercentage',        0.5),
        ('CB', v_tiro,    'totalShots',                      1.0),
        ('CB', v_pase,    'accuratePassesPercentage',         0.7),
        ('CB', v_pase,    'accurateFinalThirdPasses',          0.3),
        ('CB', v_regate,  'successfulDribblesPercentage',       1.0),
        ('CB', v_defensa, 'tackles',                              0.3),
        ('CB', v_defensa, 'interceptions',                         0.3),
        ('CB', v_defensa, 'clearances',                             0.2),
        ('CB', v_defensa, 'totalDuelsWonPercentage',                0.2),
        ('CB', v_fisico,  'aerialDuelsWonPercentage',                0.6),
        ('CB', v_fisico,  'groundDuelsWonPercentage',                 0.4);

    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight)
    SELECT unnest(ARRAY['LB','RB','LWB','RWB']::player_position[]), attribute_id, stat_field, weight
    FROM position_attribute_weights WHERE position = 'CB';

    -- =================================================================
    -- PORTEROS (GK) — atributos con otro significado, pero mismo 0-100
    -- =================================================================
    INSERT INTO position_attribute_weights (position, attribute_id, stat_field, weight) VALUES
        ('GK', v_ritmo,   'groundDuelsWonPercentage',       1.0),
        ('GK', v_tiro,    'accuratePassesPercentage',         1.0),  -- salida de balón
        ('GK', v_pase,    'accuratePassesPercentage',          1.0),
        ('GK', v_regate,  'accurateFinalThirdPasses',           1.0),
        ('GK', v_defensa, 'saves',                                0.5),
        ('GK', v_defensa, 'cleanSheets',                           0.3),
        ('GK', v_defensa, 'goalsConcededInsideTheBox',              0.2),
        ('GK', v_fisico,  'aerialDuelsWonPercentage',                1.0);

    -- =================================================================
    -- MEDIA GENERAL POR POSICIÓN (position_overall_weights)
    -- =================================================================
    INSERT INTO position_overall_weights (position, attribute_id, weight) VALUES
        ('ST', v_tiro, 0.35), ('ST', v_regate, 0.25), ('ST', v_ritmo, 0.15),
        ('ST', v_pase, 0.15), ('ST', v_fisico, 0.05), ('ST', v_defensa, 0.05);

    INSERT INTO position_overall_weights (position, attribute_id, weight)
    SELECT unnest(ARRAY['CF','LW','RW']::player_position[]), attribute_id, weight
    FROM position_overall_weights WHERE position = 'ST';

    INSERT INTO position_overall_weights (position, attribute_id, weight) VALUES
        ('CM', v_pase, 0.30), ('CM', v_regate, 0.20), ('CM', v_defensa, 0.20),
        ('CM', v_ritmo, 0.15), ('CM', v_fisico, 0.10), ('CM', v_tiro, 0.05);

    INSERT INTO position_overall_weights (position, attribute_id, weight)
    SELECT unnest(ARRAY['CDM','CAM','LM','RM']::player_position[]), attribute_id, weight
    FROM position_overall_weights WHERE position = 'CM';

    INSERT INTO position_overall_weights (position, attribute_id, weight) VALUES
        ('CB', v_defensa, 0.40), ('CB', v_fisico, 0.25), ('CB', v_pase, 0.15),
        ('CB', v_ritmo, 0.15), ('CB', v_regate, 0.03), ('CB', v_tiro, 0.02);

    INSERT INTO position_overall_weights (position, attribute_id, weight)
    SELECT unnest(ARRAY['LB','RB','LWB','RWB']::player_position[]), attribute_id, weight
    FROM position_overall_weights WHERE position = 'CB';

    INSERT INTO position_overall_weights (position, attribute_id, weight) VALUES
        ('GK', v_defensa, 0.70), ('GK', v_pase, 0.15), ('GK', v_fisico, 0.10),
        ('GK', v_ritmo, 0.03), ('GK', v_regate, 0.01), ('GK', v_tiro, 0.01);

END $$;
