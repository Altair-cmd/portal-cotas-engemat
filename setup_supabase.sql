-- ============================================================
-- Portal de Cotas ENGEMAT – Setup Supabase
-- Execute este SQL no SQL Editor do Supabase
-- https://supabase.com/dashboard/project/zafjezwrblyftnhxwmvj/sql
-- ============================================================

-- Criar tabela obras
CREATE TABLE IF NOT EXISTS obras (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  tipo          TEXT,
  cnpj          TEXT,
  obra          TEXT NOT NULL,
  emp_sienge    TEXT,
  emp_dom       TEXT,
  cc_dom        TEXT,
  qtd_func      INTEGER DEFAULT 0,
  nec_apr       INTEGER DEFAULT 0,
  atual_apr     INTEGER DEFAULT 0,
  def_apr       INTEGER DEFAULT 0,
  status_apr    TEXT DEFAULT 'Dentro da cota',
  nec_pcd       INTEGER DEFAULT 0,
  atual_pcd     INTEGER DEFAULT 0,
  def_pcd       INTEGER DEFAULT 0,
  status_pcd    TEXT DEFAULT 'Dentro da cota',
  atualizado_em TIMESTAMPTZ DEFAULT NOW()
);

-- Habilitar Row Level Security
ALTER TABLE obras ENABLE ROW LEVEL SECURITY;

-- Permitir todas as operações (autenticação é feita pelo Flask)
CREATE POLICY "Permitir tudo" ON obras
  FOR ALL USING (true) WITH CHECK (true);

-- Índice para busca rápida por obra
CREATE INDEX IF NOT EXISTS idx_obras_obra ON obras(obra);
CREATE INDEX IF NOT EXISTS idx_obras_tipo ON obras(tipo);

-- Confirmar criação
SELECT 'Tabela obras criada com sucesso!' as resultado;
