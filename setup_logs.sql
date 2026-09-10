-- ============================================================
-- Portal de Cotas ENGEMAT – Tabela de Logs
-- Execute este SQL no SQL Editor do Supabase
-- ============================================================

CREATE TABLE IF NOT EXISTS logs (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  data_hora     TIMESTAMPTZ DEFAULT NOW(),
  usuario       TEXT NOT NULL,
  acao          TEXT NOT NULL,
  detalhes      TEXT
);

-- Habilitar segurança
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;

-- Permitir todas as operações de log via backend
CREATE POLICY "Permitir tudo logs" ON logs
  FOR ALL USING (true) WITH CHECK (true);

-- Confirmar
SELECT 'Tabela logs criada com sucesso!' as resultado;
