--
-- PostgreSQL database dump
--

\restrict gbj9rHmF5jzWzdfWYtUphKfCi2Fq6JSPrzutilYS2P8RA7JQQ30bOrqIVyagjjn

-- Dumped from database version 18.4
-- Dumped by pg_dump version 18.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: agendamento_servicos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.agendamento_servicos (
    id integer NOT NULL,
    agendamento_id integer NOT NULL,
    servico_id integer NOT NULL,
    quantidade integer NOT NULL,
    preco_unitario numeric(10,2) NOT NULL,
    is_plano boolean NOT NULL,
    cliente_plano_id integer
);


ALTER TABLE public.agendamento_servicos OWNER TO postgres;

--
-- Name: agendamento_servicos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.agendamento_servicos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.agendamento_servicos_id_seq OWNER TO postgres;

--
-- Name: agendamento_servicos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.agendamento_servicos_id_seq OWNED BY public.agendamento_servicos.id;


--
-- Name: agendamento_solicitacao_pix; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.agendamento_solicitacao_pix (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    agendamento_id integer NOT NULL,
    comprovante_url character varying(255),
    status character varying(20) NOT NULL,
    motivo_rejeicao character varying(500),
    criado_em timestamp without time zone,
    respondido_em timestamp without time zone
);


ALTER TABLE public.agendamento_solicitacao_pix OWNER TO postgres;

--
-- Name: agendamento_solicitacao_pix_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.agendamento_solicitacao_pix_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.agendamento_solicitacao_pix_id_seq OWNER TO postgres;

--
-- Name: agendamento_solicitacao_pix_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.agendamento_solicitacao_pix_id_seq OWNED BY public.agendamento_solicitacao_pix.id;


--
-- Name: agendamentos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.agendamentos (
    id integer NOT NULL,
    cliente_id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    data_hora timestamp without time zone NOT NULL,
    duracao_minutos integer NOT NULL,
    status character varying(30) NOT NULL,
    valor_total numeric(10,2) NOT NULL,
    observacao character varying(300),
    metodo_pagamento character varying(20),
    criado_em timestamp without time zone,
    barbearia_id integer NOT NULL,
    cupom_id integer,
    valor_desconto numeric(10,2) DEFAULT '0'::numeric NOT NULL
);


ALTER TABLE public.agendamentos OWNER TO postgres;

--
-- Name: agendamentos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.agendamentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.agendamentos_id_seq OWNER TO postgres;

--
-- Name: agendamentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.agendamentos_id_seq OWNED BY public.agendamentos.id;


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: atendimento_itens; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.atendimento_itens (
    id integer NOT NULL,
    atendimento_id integer NOT NULL,
    tipo character varying(20) NOT NULL,
    servico_id integer,
    produto_id integer,
    preco_unitario numeric(10,2) NOT NULL,
    quantidade integer NOT NULL
);


ALTER TABLE public.atendimento_itens OWNER TO postgres;

--
-- Name: atendimento_itens_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.atendimento_itens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.atendimento_itens_id_seq OWNER TO postgres;

--
-- Name: atendimento_itens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.atendimento_itens_id_seq OWNED BY public.atendimento_itens.id;


--
-- Name: atendimentos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.atendimentos (
    id integer NOT NULL,
    agendamento_id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    cliente_id integer NOT NULL,
    status_operacao character varying(20) NOT NULL,
    total numeric(10,2),
    criado_em timestamp without time zone,
    barbearia_id integer NOT NULL
);


ALTER TABLE public.atendimentos OWNER TO postgres;

--
-- Name: atendimentos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.atendimentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.atendimentos_id_seq OWNER TO postgres;

--
-- Name: atendimentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.atendimentos_id_seq OWNED BY public.atendimentos.id;


--
-- Name: auditoria_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auditoria_log (
    id integer NOT NULL,
    usuario_id integer,
    barbearia_id integer,
    tipo_acao character varying(50) NOT NULL,
    entidade character varying(100) NOT NULL,
    entidade_id integer,
    descricao character varying(500) NOT NULL,
    criado_em timestamp without time zone
);


ALTER TABLE public.auditoria_log OWNER TO postgres;

--
-- Name: auditoria_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.auditoria_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.auditoria_log_id_seq OWNER TO postgres;

--
-- Name: auditoria_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.auditoria_log_id_seq OWNED BY public.auditoria_log.id;


--
-- Name: barbearia_customizacao; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.barbearia_customizacao (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    cor_primaria character varying(7),
    cor_secundaria character varying(7),
    cor_acentuacao character varying(7),
    texto_primario character varying(7),
    texto_secundario character varying(7),
    texto_terciario character varying(7),
    botao_primario character varying(7),
    botao_secundario character varying(7),
    logo_filename character varying(255),
    fundo_padrao_filename character varying(255),
    logo_url character varying(500),
    imagem_capa_url character varying(500),
    imagem_boas_vindas_url character varying(500),
    fonte character varying(50),
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


ALTER TABLE public.barbearia_customizacao OWNER TO postgres;

--
-- Name: barbearia_customizacao_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.barbearia_customizacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.barbearia_customizacao_id_seq OWNER TO postgres;

--
-- Name: barbearia_customizacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.barbearia_customizacao_id_seq OWNED BY public.barbearia_customizacao.id;


--
-- Name: barbearias; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.barbearias (
    id integer NOT NULL,
    nome character varying(150) NOT NULL,
    nome_exibicao character varying(150),
    slug character varying(50) NOT NULL,
    ativo boolean NOT NULL,
    url_agendamento character varying(255),
    chave_pix character varying(255),
    pix_nome_titular character varying(150),
    pix_cidade character varying(50),
    pix_banco character varying(50),
    criado_em timestamp without time zone,
    whatsapp_business_id character varying(100),
    whatsapp_phone_number_id character varying(100),
    billing_plano character varying(50),
    billing_mensalidade_valor numeric(10,2),
    billing_vencimento_dia integer,
    billing_proximo_vencimento date,
    billing_status character varying(20) NOT NULL,
    rua character varying(200),
    numero character varying(10),
    complemento character varying(100),
    bairro character varying(100),
    cidade character varying(100),
    estado character varying(2),
    cep character varying(9),
    telefone_contato character varying(20),
    instagram character varying(100),
    segmento_id integer
);


ALTER TABLE public.barbearias OWNER TO postgres;

--
-- Name: barbearias_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.barbearias_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.barbearias_id_seq OWNER TO postgres;

--
-- Name: barbearias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.barbearias_id_seq OWNED BY public.barbearias.id;


--
-- Name: barbeiro_comissao_servico; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.barbeiro_comissao_servico (
    id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    servico_id integer NOT NULL,
    barbearia_id integer NOT NULL,
    comissao_tipo character varying(20) NOT NULL,
    comissao_percentual numeric(5,2) NOT NULL,
    comissao_valor_fixo numeric(10,2) NOT NULL,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


ALTER TABLE public.barbeiro_comissao_servico OWNER TO postgres;

--
-- Name: barbeiro_comissao_servico_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.barbeiro_comissao_servico_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.barbeiro_comissao_servico_id_seq OWNER TO postgres;

--
-- Name: barbeiro_comissao_servico_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.barbeiro_comissao_servico_id_seq OWNED BY public.barbeiro_comissao_servico.id;


--
-- Name: barbeiro_servicos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.barbeiro_servicos (
    id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    servico_id integer NOT NULL
);


ALTER TABLE public.barbeiro_servicos OWNER TO postgres;

--
-- Name: barbeiro_servicos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.barbeiro_servicos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.barbeiro_servicos_id_seq OWNER TO postgres;

--
-- Name: barbeiro_servicos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.barbeiro_servicos_id_seq OWNED BY public.barbeiro_servicos.id;


--
-- Name: barbeiros; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.barbeiros (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    usuario_id integer NOT NULL,
    foto character varying(255),
    bio character varying(300),
    comissao_percentual numeric(5,2) NOT NULL,
    comissao_plano_percentual numeric(5,2) NOT NULL,
    ativo boolean NOT NULL,
    comissao_tipo character varying(20) NOT NULL,
    comissao_valor_fixo numeric(10,2) NOT NULL
);


ALTER TABLE public.barbeiros OWNER TO postgres;

--
-- Name: barbeiros_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.barbeiros_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.barbeiros_id_seq OWNER TO postgres;

--
-- Name: barbeiros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.barbeiros_id_seq OWNED BY public.barbeiros.id;


--
-- Name: cliente_notas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_notas (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    cliente_id integer NOT NULL,
    autor_usuario_id integer,
    tipo character varying(30) NOT NULL,
    conteudo text NOT NULL,
    criado_em timestamp without time zone
);


ALTER TABLE public.cliente_notas OWNER TO postgres;

--
-- Name: cliente_notas_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cliente_notas_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cliente_notas_id_seq OWNER TO postgres;

--
-- Name: cliente_notas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cliente_notas_id_seq OWNED BY public.cliente_notas.id;


--
-- Name: cliente_plano; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_plano (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    cliente_id integer NOT NULL,
    plano_id integer NOT NULL,
    barbeiro_id integer,
    data_inicio date NOT NULL,
    data_fim date,
    ativo boolean NOT NULL,
    criado_em timestamp without time zone,
    auto_renovar boolean NOT NULL
);


ALTER TABLE public.cliente_plano OWNER TO postgres;

--
-- Name: cliente_plano_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cliente_plano_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cliente_plano_id_seq OWNER TO postgres;

--
-- Name: cliente_plano_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cliente_plano_id_seq OWNED BY public.cliente_plano.id;


--
-- Name: cliente_plano_solicitacao; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_plano_solicitacao (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    cliente_id integer NOT NULL,
    plano_id integer NOT NULL,
    barbeiro_id integer,
    valor numeric(10,2) NOT NULL,
    comprovante_url character varying(255),
    metodo_pagamento character varying(20) NOT NULL,
    status character varying(20) NOT NULL,
    criado_em timestamp without time zone,
    aprovado_em timestamp without time zone,
    motivo_rejeicao character varying(500)
);


ALTER TABLE public.cliente_plano_solicitacao OWNER TO postgres;

--
-- Name: cliente_plano_solicitacao_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cliente_plano_solicitacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cliente_plano_solicitacao_id_seq OWNER TO postgres;

--
-- Name: cliente_plano_solicitacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cliente_plano_solicitacao_id_seq OWNED BY public.cliente_plano_solicitacao.id;


--
-- Name: cliente_plano_uso; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_plano_uso (
    id integer NOT NULL,
    cliente_plano_id integer NOT NULL,
    servico_id integer NOT NULL,
    data_uso date NOT NULL,
    semana_do_mes integer NOT NULL,
    usado boolean NOT NULL
);


ALTER TABLE public.cliente_plano_uso OWNER TO postgres;

--
-- Name: cliente_plano_uso_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cliente_plano_uso_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cliente_plano_uso_id_seq OWNER TO postgres;

--
-- Name: cliente_plano_uso_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cliente_plano_uso_id_seq OWNED BY public.cliente_plano_uso.id;


--
-- Name: cliente_vip; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente_vip (
    id integer NOT NULL,
    cliente_id integer NOT NULL,
    barbearia_id integer NOT NULL,
    nivel_vip_atual integer NOT NULL,
    brindes_resgatados text,
    data_proxima_renovacao date,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


ALTER TABLE public.cliente_vip OWNER TO postgres;

--
-- Name: cliente_vip_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cliente_vip_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cliente_vip_id_seq OWNER TO postgres;

--
-- Name: cliente_vip_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cliente_vip_id_seq OWNED BY public.cliente_vip.id;


--
-- Name: clientes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.clientes (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    usuario_id integer,
    nome character varying(100) NOT NULL,
    telefone character varying(20) NOT NULL,
    email character varying(150),
    foto character varying(255),
    observacoes text,
    ativo boolean NOT NULL,
    primeira_visita date,
    ultimo_acesso timestamp without time zone,
    notif_sms boolean NOT NULL,
    notif_whatsapp boolean NOT NULL,
    notif_email boolean NOT NULL,
    data_nascimento date,
    criado_em timestamp without time zone,
    barbeiro_preferido_id integer,
    saldo_creditos numeric(10,2) NOT NULL,
    whatsapp_opt_in boolean NOT NULL
);


ALTER TABLE public.clientes OWNER TO postgres;

--
-- Name: clientes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.clientes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.clientes_id_seq OWNER TO postgres;

--
-- Name: clientes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.clientes_id_seq OWNED BY public.clientes.id;


--
-- Name: configuracao_agenda; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.configuracao_agenda (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    horario_abertura time without time zone NOT NULL,
    horario_fechamento time without time zone NOT NULL,
    intervalo_minutos integer NOT NULL,
    loja_aberta boolean NOT NULL,
    atualizado_em timestamp without time zone,
    permite_horario_barbeiro boolean DEFAULT false NOT NULL
);


ALTER TABLE public.configuracao_agenda OWNER TO postgres;

--
-- Name: configuracao_agenda_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.configuracao_agenda_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.configuracao_agenda_id_seq OWNER TO postgres;

--
-- Name: configuracao_agenda_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.configuracao_agenda_id_seq OWNED BY public.configuracao_agenda.id;


--
-- Name: configuracao_agendamento; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.configuracao_agendamento (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    cancelamento_horas_minimas integer NOT NULL,
    permite_multi_servico boolean NOT NULL,
    quick_booking_sem_login boolean NOT NULL,
    intervalo_slot_minutos integer NOT NULL,
    antecedencia_maxima_dias integer NOT NULL,
    notif_antecedencia_cliente_min integer CONSTRAINT configuracao_agendamento_notif_antecedencia_cliente_mi_not_null NOT NULL,
    notif_antecedencia_barbeiro_min integer CONSTRAINT configuracao_agendamento_notif_antecedencia_barbeiro_m_not_null NOT NULL,
    atualizado_em timestamp without time zone
);


ALTER TABLE public.configuracao_agendamento OWNER TO postgres;

--
-- Name: configuracao_agendamento_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.configuracao_agendamento_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.configuracao_agendamento_id_seq OWNER TO postgres;

--
-- Name: configuracao_agendamento_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.configuracao_agendamento_id_seq OWNED BY public.configuracao_agendamento.id;


--
-- Name: cupons; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cupons (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    nome character varying(100) NOT NULL,
    codigo character varying(30) NOT NULL,
    tipo_desconto character varying(20) NOT NULL,
    valor_desconto numeric(10,2) NOT NULL,
    data_expiracao date NOT NULL,
    quantidade_maxima_usos integer,
    quantidade_usos integer DEFAULT 0 NOT NULL,
    ativo boolean DEFAULT true NOT NULL,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone
);


ALTER TABLE public.cupons OWNER TO postgres;

--
-- Name: cupons_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.cupons_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.cupons_id_seq OWNER TO postgres;

--
-- Name: cupons_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.cupons_id_seq OWNED BY public.cupons.id;


--
-- Name: feature_barbearia; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.feature_barbearia (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    feature_id integer NOT NULL,
    ativo boolean NOT NULL,
    atualizado_em timestamp without time zone
);


ALTER TABLE public.feature_barbearia OWNER TO postgres;

--
-- Name: feature_barbearia_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.feature_barbearia_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.feature_barbearia_id_seq OWNER TO postgres;

--
-- Name: feature_barbearia_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.feature_barbearia_id_seq OWNED BY public.feature_barbearia.id;


--
-- Name: feature_metadata; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.feature_metadata (
    id integer NOT NULL,
    nome character varying(50) NOT NULL,
    descricao character varying(200)
);


ALTER TABLE public.feature_metadata OWNER TO postgres;

--
-- Name: feature_metadata_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.feature_metadata_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.feature_metadata_id_seq OWNER TO postgres;

--
-- Name: feature_metadata_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.feature_metadata_id_seq OWNED BY public.feature_metadata.id;


--
-- Name: fila_espera; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fila_espera (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    cliente_id integer NOT NULL,
    barbeiro_preferido_id integer,
    servico_id integer,
    data_preferida date,
    prioridade integer NOT NULL,
    posicao integer NOT NULL,
    status character varying(20) NOT NULL,
    chamado_em timestamp without time zone,
    criado_em timestamp without time zone
);


ALTER TABLE public.fila_espera OWNER TO postgres;

--
-- Name: fila_espera_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fila_espera_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fila_espera_id_seq OWNER TO postgres;

--
-- Name: fila_espera_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fila_espera_id_seq OWNED BY public.fila_espera.id;


--
-- Name: horarios_bloqueados; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.horarios_bloqueados (
    id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    data_hora_inicio timestamp without time zone NOT NULL,
    data_hora_fim timestamp without time zone NOT NULL,
    motivo character varying(100),
    barbearia_id integer NOT NULL
);


ALTER TABLE public.horarios_bloqueados OWNER TO postgres;

--
-- Name: horarios_bloqueados_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.horarios_bloqueados_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.horarios_bloqueados_id_seq OWNER TO postgres;

--
-- Name: horarios_bloqueados_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.horarios_bloqueados_id_seq OWNED BY public.horarios_bloqueados.id;


--
-- Name: notificacoes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notificacoes (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    usuario_id integer NOT NULL,
    agendamento_id integer,
    tipo character varying(50) NOT NULL,
    canal character varying(20) NOT NULL,
    titulo character varying(200) NOT NULL,
    corpo character varying(1000) NOT NULL,
    lida boolean NOT NULL,
    enviada boolean NOT NULL,
    criado_em timestamp without time zone
);


ALTER TABLE public.notificacoes OWNER TO postgres;

--
-- Name: notificacoes_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.notificacoes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.notificacoes_id_seq OWNER TO postgres;

--
-- Name: notificacoes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.notificacoes_id_seq OWNED BY public.notificacoes.id;


--
-- Name: pagamentos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pagamentos (
    id integer NOT NULL,
    atendimento_id integer NOT NULL,
    forma_pagamento character varying(30) NOT NULL,
    valor numeric(10,2) NOT NULL,
    status character varying(20) NOT NULL,
    gateway character varying(30),
    gateway_transaction_id character varying(100),
    criado_em timestamp without time zone,
    gateway_status character varying(50),
    gateway_metadata text
);


ALTER TABLE public.pagamentos OWNER TO postgres;

--
-- Name: pagamentos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pagamentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pagamentos_id_seq OWNER TO postgres;

--
-- Name: pagamentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pagamentos_id_seq OWNED BY public.pagamentos.id;


--
-- Name: pausa_barbeiro; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pausa_barbeiro (
    id integer NOT NULL,
    barbearia_id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    hora_inicio time without time zone NOT NULL,
    hora_fim time without time zone NOT NULL,
    descricao character varying(50),
    criado_em timestamp without time zone
);


ALTER TABLE public.pausa_barbeiro OWNER TO postgres;

--
-- Name: pausa_barbeiro_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pausa_barbeiro_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pausa_barbeiro_id_seq OWNER TO postgres;

--
-- Name: pausa_barbeiro_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pausa_barbeiro_id_seq OWNED BY public.pausa_barbeiro.id;


--
-- Name: plano_barbeiros; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plano_barbeiros (
    id integer NOT NULL,
    plano_id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    barbearia_id integer NOT NULL,
    adicionado_em timestamp without time zone
);


ALTER TABLE public.plano_barbeiros OWNER TO postgres;

--
-- Name: plano_barbeiros_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.plano_barbeiros_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.plano_barbeiros_id_seq OWNER TO postgres;

--
-- Name: plano_barbeiros_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.plano_barbeiros_id_seq OWNED BY public.plano_barbeiros.id;


--
-- Name: plano_servicos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.plano_servicos (
    id integer NOT NULL,
    plano_id integer NOT NULL,
    servico_id integer NOT NULL,
    limite_uso_mensal integer NOT NULL,
    dias_expiracao integer NOT NULL,
    ativo boolean NOT NULL
);


ALTER TABLE public.plano_servicos OWNER TO postgres;

--
-- Name: plano_servicos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.plano_servicos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.plano_servicos_id_seq OWNER TO postgres;

--
-- Name: plano_servicos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.plano_servicos_id_seq OWNED BY public.plano_servicos.id;


--
-- Name: planos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.planos (
    id integer NOT NULL,
    barbeiro_id integer,
    nome character varying(150) NOT NULL,
    descricao text,
    preco_mensal numeric(10,2) NOT NULL,
    ativo boolean NOT NULL,
    criado_em timestamp without time zone,
    atualizado_em timestamp without time zone,
    trial_dias integer NOT NULL,
    max_assinaturas integer,
    barbearia_id integer NOT NULL
);


ALTER TABLE public.planos OWNER TO postgres;

--
-- Name: planos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.planos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.planos_id_seq OWNER TO postgres;

--
-- Name: planos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.planos_id_seq OWNED BY public.planos.id;


--
-- Name: produtos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.produtos (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    categoria character varying(50),
    preco numeric(10,2) NOT NULL,
    quantidade_estoque integer NOT NULL,
    quantidade_reservada integer NOT NULL,
    foto character varying(255),
    ativo boolean NOT NULL,
    criado_em timestamp without time zone,
    barbearia_id integer NOT NULL
);


ALTER TABLE public.produtos OWNER TO postgres;

--
-- Name: produtos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.produtos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.produtos_id_seq OWNER TO postgres;

--
-- Name: produtos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.produtos_id_seq OWNED BY public.produtos.id;


--
-- Name: reservas_produtos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.reservas_produtos (
    id integer NOT NULL,
    agendamento_id integer NOT NULL,
    produto_id integer NOT NULL,
    quantidade integer NOT NULL,
    status character varying(20) NOT NULL
);


ALTER TABLE public.reservas_produtos OWNER TO postgres;

--
-- Name: reservas_produtos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.reservas_produtos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.reservas_produtos_id_seq OWNER TO postgres;

--
-- Name: reservas_produtos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.reservas_produtos_id_seq OWNED BY public.reservas_produtos.id;


--
-- Name: segmento_rotulos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.segmento_rotulos (
    id integer NOT NULL,
    segmento_id integer NOT NULL,
    rotulo_tenant character varying(50),
    rotulo_tenant_plural character varying(50),
    rotulo_profissional character varying(50),
    rotulo_profissional_plural character varying(50),
    rotulo_servico character varying(50),
    rotulo_servico_plural character varying(50),
    rotulo_agendamento character varying(50),
    rotulo_agendamento_plural character varying(50),
    rotulo_cliente character varying(50),
    rotulo_cliente_plural character varying(50),
    rotulo_produto character varying(50),
    rotulo_produto_plural character varying(50),
    rotulo_plano character varying(50),
    rotulo_plano_plural character varying(50),
    rotulo_pagamento character varying(50),
    rotulo_faturamento character varying(50),
    rotulo_relatorio character varying(50),
    atualizado_em timestamp without time zone
);


ALTER TABLE public.segmento_rotulos OWNER TO postgres;

--
-- Name: segmento_rotulos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.segmento_rotulos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.segmento_rotulos_id_seq OWNER TO postgres;

--
-- Name: segmento_rotulos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.segmento_rotulos_id_seq OWNED BY public.segmento_rotulos.id;


--
-- Name: segmentos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.segmentos (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    chave character varying(50) NOT NULL
);


ALTER TABLE public.segmentos OWNER TO postgres;

--
-- Name: segmentos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.segmentos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.segmentos_id_seq OWNER TO postgres;

--
-- Name: segmentos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.segmentos_id_seq OWNED BY public.segmentos.id;


--
-- Name: servicos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.servicos (
    id integer NOT NULL,
    nome character varying(100) NOT NULL,
    descricao character varying(300),
    duracao_minutos integer NOT NULL,
    preco numeric(10,2) NOT NULL,
    foto character varying(255),
    ativo boolean NOT NULL,
    barbearia_id integer NOT NULL
);


ALTER TABLE public.servicos OWNER TO postgres;

--
-- Name: servicos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.servicos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.servicos_id_seq OWNER TO postgres;

--
-- Name: servicos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.servicos_id_seq OWNED BY public.servicos.id;


--
-- Name: solicitacoes_liberacao; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.solicitacoes_liberacao (
    id integer NOT NULL,
    barbeiro_id integer NOT NULL,
    data date NOT NULL,
    hora_inicio time without time zone,
    hora_fim time without time zone,
    motivo character varying(300),
    status character varying(20) NOT NULL,
    notificado boolean NOT NULL,
    data_solicitacao timestamp without time zone,
    data_resposta timestamp without time zone,
    barbearia_id integer NOT NULL
);


ALTER TABLE public.solicitacoes_liberacao OWNER TO postgres;

--
-- Name: solicitacoes_liberacao_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.solicitacoes_liberacao_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.solicitacoes_liberacao_id_seq OWNER TO postgres;

--
-- Name: solicitacoes_liberacao_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.solicitacoes_liberacao_id_seq OWNED BY public.solicitacoes_liberacao.id;


--
-- Name: solicitacoes_senha; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.solicitacoes_senha (
    id integer NOT NULL,
    usuario_id integer NOT NULL,
    barbearia_id integer NOT NULL,
    status character varying(20) NOT NULL,
    criado_em timestamp without time zone
);


ALTER TABLE public.solicitacoes_senha OWNER TO postgres;

--
-- Name: solicitacoes_senha_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.solicitacoes_senha_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.solicitacoes_senha_id_seq OWNER TO postgres;

--
-- Name: solicitacoes_senha_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.solicitacoes_senha_id_seq OWNED BY public.solicitacoes_senha.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    barbearia_id integer,
    nome character varying(100) NOT NULL,
    telefone character varying(20) NOT NULL,
    email character varying(100),
    senha character varying(255),
    perfil character varying(20) NOT NULL,
    ativo boolean NOT NULL,
    foto_perfil_url character varying(255),
    data_nascimento date,
    criado_em timestamp without time zone,
    duplo_fator_ativo boolean NOT NULL,
    duplo_fator_segredo character varying(64),
    whatsapp_verificado boolean NOT NULL
);


ALTER TABLE public.usuarios OWNER TO postgres;

--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usuarios_id_seq OWNER TO postgres;

--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: vip_niveis; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vip_niveis (
    id integer NOT NULL,
    nivel integer NOT NULL,
    brinde_descricao text NOT NULL,
    tipo_brinde character varying(20) NOT NULL,
    valor_desconto numeric(10,2),
    ativo boolean NOT NULL,
    modo_brinde_ativo boolean NOT NULL,
    criado_em timestamp without time zone,
    barbearia_id integer NOT NULL
);


ALTER TABLE public.vip_niveis OWNER TO postgres;

--
-- Name: vip_niveis_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.vip_niveis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.vip_niveis_id_seq OWNER TO postgres;

--
-- Name: vip_niveis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.vip_niveis_id_seq OWNED BY public.vip_niveis.id;


--
-- Name: agendamento_servicos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_servicos ALTER COLUMN id SET DEFAULT nextval('public.agendamento_servicos_id_seq'::regclass);


--
-- Name: agendamento_solicitacao_pix id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_solicitacao_pix ALTER COLUMN id SET DEFAULT nextval('public.agendamento_solicitacao_pix_id_seq'::regclass);


--
-- Name: agendamentos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamentos ALTER COLUMN id SET DEFAULT nextval('public.agendamentos_id_seq'::regclass);


--
-- Name: atendimento_itens id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimento_itens ALTER COLUMN id SET DEFAULT nextval('public.atendimento_itens_id_seq'::regclass);


--
-- Name: atendimentos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos ALTER COLUMN id SET DEFAULT nextval('public.atendimentos_id_seq'::regclass);


--
-- Name: auditoria_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auditoria_log ALTER COLUMN id SET DEFAULT nextval('public.auditoria_log_id_seq'::regclass);


--
-- Name: barbearia_customizacao id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearia_customizacao ALTER COLUMN id SET DEFAULT nextval('public.barbearia_customizacao_id_seq'::regclass);


--
-- Name: barbearias id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearias ALTER COLUMN id SET DEFAULT nextval('public.barbearias_id_seq'::regclass);


--
-- Name: barbeiro_comissao_servico id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_comissao_servico ALTER COLUMN id SET DEFAULT nextval('public.barbeiro_comissao_servico_id_seq'::regclass);


--
-- Name: barbeiro_servicos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_servicos ALTER COLUMN id SET DEFAULT nextval('public.barbeiro_servicos_id_seq'::regclass);


--
-- Name: barbeiros id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiros ALTER COLUMN id SET DEFAULT nextval('public.barbeiros_id_seq'::regclass);


--
-- Name: cliente_notas id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_notas ALTER COLUMN id SET DEFAULT nextval('public.cliente_notas_id_seq'::regclass);


--
-- Name: cliente_plano id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano ALTER COLUMN id SET DEFAULT nextval('public.cliente_plano_id_seq'::regclass);


--
-- Name: cliente_plano_solicitacao id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_solicitacao ALTER COLUMN id SET DEFAULT nextval('public.cliente_plano_solicitacao_id_seq'::regclass);


--
-- Name: cliente_plano_uso id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_uso ALTER COLUMN id SET DEFAULT nextval('public.cliente_plano_uso_id_seq'::regclass);


--
-- Name: cliente_vip id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_vip ALTER COLUMN id SET DEFAULT nextval('public.cliente_vip_id_seq'::regclass);


--
-- Name: clientes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes ALTER COLUMN id SET DEFAULT nextval('public.clientes_id_seq'::regclass);


--
-- Name: configuracao_agenda id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agenda ALTER COLUMN id SET DEFAULT nextval('public.configuracao_agenda_id_seq'::regclass);


--
-- Name: configuracao_agendamento id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agendamento ALTER COLUMN id SET DEFAULT nextval('public.configuracao_agendamento_id_seq'::regclass);


--
-- Name: cupons id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cupons ALTER COLUMN id SET DEFAULT nextval('public.cupons_id_seq'::regclass);


--
-- Name: feature_barbearia id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_barbearia ALTER COLUMN id SET DEFAULT nextval('public.feature_barbearia_id_seq'::regclass);


--
-- Name: feature_metadata id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_metadata ALTER COLUMN id SET DEFAULT nextval('public.feature_metadata_id_seq'::regclass);


--
-- Name: fila_espera id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fila_espera ALTER COLUMN id SET DEFAULT nextval('public.fila_espera_id_seq'::regclass);


--
-- Name: horarios_bloqueados id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.horarios_bloqueados ALTER COLUMN id SET DEFAULT nextval('public.horarios_bloqueados_id_seq'::regclass);


--
-- Name: notificacoes id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificacoes ALTER COLUMN id SET DEFAULT nextval('public.notificacoes_id_seq'::regclass);


--
-- Name: pagamentos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pagamentos ALTER COLUMN id SET DEFAULT nextval('public.pagamentos_id_seq'::regclass);


--
-- Name: pausa_barbeiro id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pausa_barbeiro ALTER COLUMN id SET DEFAULT nextval('public.pausa_barbeiro_id_seq'::regclass);


--
-- Name: plano_barbeiros id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_barbeiros ALTER COLUMN id SET DEFAULT nextval('public.plano_barbeiros_id_seq'::regclass);


--
-- Name: plano_servicos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_servicos ALTER COLUMN id SET DEFAULT nextval('public.plano_servicos_id_seq'::regclass);


--
-- Name: planos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planos ALTER COLUMN id SET DEFAULT nextval('public.planos_id_seq'::regclass);


--
-- Name: produtos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.produtos ALTER COLUMN id SET DEFAULT nextval('public.produtos_id_seq'::regclass);


--
-- Name: reservas_produtos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservas_produtos ALTER COLUMN id SET DEFAULT nextval('public.reservas_produtos_id_seq'::regclass);


--
-- Name: segmento_rotulos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmento_rotulos ALTER COLUMN id SET DEFAULT nextval('public.segmento_rotulos_id_seq'::regclass);


--
-- Name: segmentos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmentos ALTER COLUMN id SET DEFAULT nextval('public.segmentos_id_seq'::regclass);


--
-- Name: servicos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servicos ALTER COLUMN id SET DEFAULT nextval('public.servicos_id_seq'::regclass);


--
-- Name: solicitacoes_liberacao id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_liberacao ALTER COLUMN id SET DEFAULT nextval('public.solicitacoes_liberacao_id_seq'::regclass);


--
-- Name: solicitacoes_senha id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_senha ALTER COLUMN id SET DEFAULT nextval('public.solicitacoes_senha_id_seq'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Name: vip_niveis id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vip_niveis ALTER COLUMN id SET DEFAULT nextval('public.vip_niveis_id_seq'::regclass);


--
-- Data for Name: agendamento_servicos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.agendamento_servicos (id, agendamento_id, servico_id, quantidade, preco_unitario, is_plano, cliente_plano_id) FROM stdin;
1	1	1	1	40.00	f	\N
2	2	1	1	40.00	f	\N
3	3	1	1	40.00	f	\N
4	3	2	1	30.00	f	\N
5	4	2	1	30.00	f	\N
6	4	1	1	40.00	f	\N
7	5	2	1	30.00	f	\N
8	5	3	1	20.00	f	\N
9	6	2	1	30.00	f	\N
10	6	3	1	20.00	f	\N
11	7	1	1	40.00	f	\N
12	8	2	1	30.00	f	\N
13	9	1	1	40.00	f	\N
14	10	2	1	30.00	f	\N
15	11	3	1	20.00	f	\N
16	12	3	1	20.00	f	\N
17	13	3	1	20.00	f	\N
19	15	1	1	40.00	f	\N
\.


--
-- Data for Name: agendamento_solicitacao_pix; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.agendamento_solicitacao_pix (id, barbearia_id, agendamento_id, comprovante_url, status, motivo_rejeicao, criado_em, respondido_em) FROM stdin;
2	1	3	\N	pendente	\N	2026-06-29 15:54:50.553832	\N
3	1	4	\N	pendente	\N	2026-06-29 16:07:11.293807	\N
4	1	5	\N	pendente	\N	2026-06-29 16:09:36.52024	\N
1	1	2	\N	rejeitado	\N	2026-06-29 15:22:18.212385	\N
5	1	6	https://res.cloudinary.com/dftntop4j/image/upload/v1782777262/barbearia/1/comprovantes/2026/06/ag_6.png	aprovado	\N	2026-06-29 19:53:56.951933	2026-06-29 23:55:55.287799
6	1	8	\N	pendente	\N	2026-06-29 20:15:54.174864	\N
7	1	15	\N	pendente	\N	2026-06-30 12:35:05.475521	\N
\.


--
-- Data for Name: agendamentos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.agendamentos (id, cliente_id, barbeiro_id, data_hora, duracao_minutos, status, valor_total, observacao, metodo_pagamento, criado_em, barbearia_id, cupom_id, valor_desconto) FROM stdin;
1	1	1	2026-07-01 10:00:00	45	agendado	40.00	\N	local	2026-06-29 18:04:44.892806	1	\N	0.00
3	2	1	2026-06-30 08:45:00	65	aguardando_pagamento	70.00	\N	pix	2026-06-29 15:54:50.54446	1	\N	0.00
4	3	1	2026-06-30 13:15:00	65	aguardando_pagamento	70.00	\N	pix	2026-06-29 16:07:11.287289	1	\N	0.00
5	2	1	2026-06-30 17:00:00	40	aguardando_pagamento	50.00	\N	pix	2026-06-29 16:09:36.515275	1	\N	0.00
2	2	1	2026-06-29 17:00:00	45	cancelado	40.00	\N	pix	2026-06-29 15:22:18.20572	1	\N	0.00
6	2	1	2026-06-30 15:30:00	40	agendado	50.00	\N	pix	2026-06-29 19:53:56.944272	1	\N	0.00
7	2	1	2026-06-30 11:00:00	45	agendado	40.00	\N	local	2026-06-29 20:13:57.549111	1	\N	0.00
8	4	1	2026-06-30 18:30:00	20	aguardando_comprovante	30.00	\N	pix	2026-06-29 20:15:54.172207	1	\N	0.00
9	6	1	2026-07-01 11:00:00	45	cancelado	40.00	cancelamento de teste QA	local	2026-06-30 09:45:18.048556	1	\N	0.00
10	7	1	2026-07-02 09:30:00	20	cancelado	30.00	\N	local	2026-06-30 09:46:31.487551	1	\N	0.00
13	8	1	2026-07-04 11:00:00	20	cancelado	15.00	\N	local	2026-06-30 10:38:22.292407	1	3	5.00
12	9	1	2026-07-03 11:00:00	20	cancelado	20.00	cleanup QA	local	2026-06-30 09:56:05.601481	1	\N	0.00
11	8	1	2026-06-30 11:49:13.730327	20	cancelado	20.00	 [cleanup QA]	local	2026-06-30 09:48:59.23286	1	\N	0.00
15	12	1	2026-06-30 17:45:00	45	aguardando_comprovante	40.00	\N	pix	2026-06-30 12:35:05.469696	1	\N	0.00
\.


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
843668e4f632
\.


--
-- Data for Name: atendimento_itens; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.atendimento_itens (id, atendimento_id, tipo, servico_id, produto_id, preco_unitario, quantidade) FROM stdin;
\.


--
-- Data for Name: atendimentos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.atendimentos (id, agendamento_id, barbeiro_id, cliente_id, status_operacao, total, criado_em, barbearia_id) FROM stdin;
\.


--
-- Data for Name: auditoria_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.auditoria_log (id, usuario_id, barbearia_id, tipo_acao, entidade, entidade_id, descricao, criado_em) FROM stdin;
\.


--
-- Data for Name: barbearia_customizacao; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.barbearia_customizacao (id, barbearia_id, cor_primaria, cor_secundaria, cor_acentuacao, texto_primario, texto_secundario, texto_terciario, botao_primario, botao_secundario, logo_filename, fundo_padrao_filename, logo_url, imagem_capa_url, imagem_boas_vindas_url, fonte, criado_em, atualizado_em) FROM stdin;
2	2	#BA7517	#1a1a1a	#FFD700	#FFFFFF	#CCCCCC	#888888	#FFD700	#555555	\N	\N	\N	\N	\N	Inter	2026-06-29 03:45:16.639075	2026-06-29 19:03:28.813404
3	3	#ba1797	#1a1a1a	#FFD700	#FFFFFF	#CCCCCC	#888888	#FFD700	#555555	\N	\N	\N	\N	\N	Inter	2026-06-29 19:13:17.338759	2026-06-29 19:13:41.457863
1	1	#fec904	#1a1a1a	#FFD700	#FFFFFF	#CCCCCC	#888888	#FFD700	#555555	\N	\N	https://res.cloudinary.com/dftntop4j/image/upload/v1782699878/barberos/customizacao/barbearia_1_logo.png	https://res.cloudinary.com/dftntop4j/image/upload/v1782776845/barberos/customizacao/barbearia_1_capa.png	https://res.cloudinary.com/dftntop4j/image/upload/v1782778381/barberos/customizacao/barbearia_1_boas_vindas.png	Inter	2026-06-29 02:21:56.484061	2026-06-29 20:13:02.807376
\.


--
-- Data for Name: barbearias; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.barbearias (id, nome, nome_exibicao, slug, ativo, url_agendamento, chave_pix, pix_nome_titular, pix_cidade, pix_banco, criado_em, whatsapp_business_id, whatsapp_phone_number_id, billing_plano, billing_mensalidade_valor, billing_vencimento_dia, billing_proximo_vencimento, billing_status, rua, numero, complemento, bairro, cidade, estado, cep, telefone_contato, instagram, segmento_id) FROM stdin;
2	Barbearia Teste Auto	Teste Auto	teste-auto	t	\N	\N	\N	\N	\N	2026-06-29 03:45:16.47446	\N	\N	\N	\N	\N	\N	em_dia	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
3	teste1	teste1	teste1	t	\N	\N	\N	\N	\N	2026-06-29 19:13:17.169652	\N	\N	\N	\N	\N	\N	em_dia	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
1	Winner BarberShop	Winner-BarberShop	winner-barbershop	t	\N	69992825997	Victor Winner Granville	cerejeiras	\N	2026-06-29 02:21:56.321365	\N	\N	\N	\N	\N	\N	em_dia	Rua:  Portugal	1717	BARBEARIA	CENTRO	Cerejeiras	RO	76997000	\N	@_barbeiro.winner	\N
\.


--
-- Data for Name: barbeiro_comissao_servico; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.barbeiro_comissao_servico (id, barbeiro_id, servico_id, barbearia_id, comissao_tipo, comissao_percentual, comissao_valor_fixo, criado_em, atualizado_em) FROM stdin;
\.


--
-- Data for Name: barbeiro_servicos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.barbeiro_servicos (id, barbeiro_id, servico_id) FROM stdin;
1	1	1
2	1	2
3	1	3
4	1	4
\.


--
-- Data for Name: barbeiros; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.barbeiros (id, barbearia_id, usuario_id, foto, bio, comissao_percentual, comissao_plano_percentual, ativo, comissao_tipo, comissao_valor_fixo) FROM stdin;
1	1	4	\N	\N	100.00	0.00	t	percentual	0.00
\.


--
-- Data for Name: cliente_notas; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_notas (id, barbearia_id, cliente_id, autor_usuario_id, tipo, conteudo, criado_em) FROM stdin;
1	1	2	4	preferencia	prefere degrade	2026-06-29 20:05:35.002211
2	1	2	4	alerta	sencibilidade	2026-06-29 20:06:52.325226
\.


--
-- Data for Name: cliente_plano; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_plano (id, barbearia_id, cliente_id, plano_id, barbeiro_id, data_inicio, data_fim, ativo, criado_em, auto_renovar) FROM stdin;
\.


--
-- Data for Name: cliente_plano_solicitacao; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_plano_solicitacao (id, barbearia_id, cliente_id, plano_id, barbeiro_id, valor, comprovante_url, metodo_pagamento, status, criado_em, aprovado_em, motivo_rejeicao) FROM stdin;
1	1	13	3	\N	400.00	\N	dinheiro	pendente	2026-06-30 19:05:41.954541	\N	\N
\.


--
-- Data for Name: cliente_plano_uso; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_plano_uso (id, cliente_plano_id, servico_id, data_uso, semana_do_mes, usado) FROM stdin;
\.


--
-- Data for Name: cliente_vip; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente_vip (id, cliente_id, barbearia_id, nivel_vip_atual, brindes_resgatados, data_proxima_renovacao, criado_em, atualizado_em) FROM stdin;
\.


--
-- Data for Name: clientes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.clientes (id, barbearia_id, usuario_id, nome, telefone, email, foto, observacoes, ativo, primeira_visita, ultimo_acesso, notif_sms, notif_whatsapp, notif_email, data_nascimento, criado_em, barbeiro_preferido_id, saldo_creditos, whatsapp_opt_in) FROM stdin;
1	1	\N	Cliente Teste LEVA3	11987654321	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-29 18:04:44.865181	\N	0.00	f
2	1	\N	alceno	69999999998	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-29 15:22:18.185031	\N	0.00	f
3	1	\N	Teste QA	85987654321	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-29 16:07:11.268678	\N	0.00	f
4	1	\N	alceno AGUIAR	69999999997	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-29 20:15:54.16413	\N	0.00	f
6	1	\N	QA Teste Smoke	11900001234	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-30 09:45:18.025752	\N	0.00	f
7	1	7	QA Cliente Smoke	11900005678	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-30 09:46:31.421243	\N	0.00	f
8	1	8	QA Cliente Cutoff	11900009999	qa.cutoff@teste.com	\N	\N	t	\N	\N	t	t	t	\N	2026-06-30 09:48:59.211244	\N	0.00	f
9	1	\N	QA Teste Cupom	11900001235	\N	\N	\N	t	\N	\N	t	t	t	\N	2026-06-30 09:56:05.567639	\N	0.00	f
12	1	9	alceno aguiar	69993921709	idprimeweb01@gmail.com	\N	\N	t	\N	\N	t	t	t	\N	2026-06-30 12:34:13.734356	\N	0.00	f
13	1	10	teste1	69998765431	teste1@cliente.com	\N	\N	t	\N	\N	t	t	t	\N	2026-06-30 12:40:06.091021	\N	0.00	f
\.


--
-- Data for Name: configuracao_agenda; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.configuracao_agenda (id, barbearia_id, barbeiro_id, horario_abertura, horario_fechamento, intervalo_minutos, loja_aberta, atualizado_em, permite_horario_barbeiro) FROM stdin;
1	1	1	09:30:00	19:00:00	45	t	2026-06-29 19:57:29.938935	t
\.


--
-- Data for Name: configuracao_agendamento; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.configuracao_agendamento (id, barbearia_id, cancelamento_horas_minimas, permite_multi_servico, quick_booking_sem_login, intervalo_slot_minutos, antecedencia_maxima_dias, notif_antecedencia_cliente_min, notif_antecedencia_barbeiro_min, atualizado_em) FROM stdin;
1	1	3	t	t	15	60	30	15	2026-06-29 02:21:56.49036
2	2	3	t	t	15	60	30	15	2026-06-29 03:45:16.642263
3	3	3	t	t	15	60	30	15	2026-06-29 19:13:17.345018
\.


--
-- Data for Name: cupons; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cupons (id, barbearia_id, nome, codigo, tipo_desconto, valor_desconto, data_expiracao, quantidade_maxima_usos, quantidade_usos, ativo, criado_em, atualizado_em) FROM stdin;
2	1	QA Teste Expirado	QATEST1	percentual	10.00	2026-06-29	5	0	f	2026-06-30 09:55:24.816903	2026-06-30 10:38:45.432944
3	1	QA Teste Valido	QATEST2	valor_fixo	5.00	2026-07-05	5	0	f	2026-06-30 09:55:24.838467	2026-06-30 10:38:45.63037
\.


--
-- Data for Name: feature_barbearia; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.feature_barbearia (id, barbearia_id, feature_id, ativo, atualizado_em) FROM stdin;
3	1	10	t	2026-06-29 17:35:06.388397
4	1	4	t	2026-06-29 17:35:08.379537
5	1	5	t	2026-06-29 17:35:09.35713
8	1	2	t	2026-06-29 17:35:17.561468
9	1	8	t	2026-06-29 17:35:18.571763
7	1	7	f	2026-06-29 19:11:29.619222
10	1	9	f	2026-06-29 19:12:06.697479
11	3	1	f	2026-06-29 19:13:17.352817
12	3	2	f	2026-06-29 19:13:17.352821
13	3	3	f	2026-06-29 19:13:17.352822
15	3	5	f	2026-06-29 19:13:17.352824
16	3	6	f	2026-06-29 19:13:17.352825
17	3	7	f	2026-06-29 19:13:17.352826
18	3	8	f	2026-06-29 19:13:17.352827
19	3	9	f	2026-06-29 19:13:17.352828
20	3	10	f	2026-06-29 19:13:17.352829
14	3	4	t	2026-06-29 19:13:32.151603
6	1	6	f	2026-06-30 10:38:45.997066
1	1	1	t	2026-06-30 19:22:05.312474
2	1	3	f	2026-06-30 19:22:06.623753
\.


--
-- Data for Name: feature_metadata; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.feature_metadata (id, nome, descricao) FROM stdin;
1	planos	Planos de assinatura mensal para clientes
2	relatorios_avancados	Relatórios customizáveis e exportação Excel/PDF
3	vip_brindes	Programa VIP com níveis e brindes por fidelidade
4	agendamento_login	Exige login do cliente para agendar online
5	historico_cliente	Histórico completo de atendimentos por cliente
6	cupons	Cupons de desconto para clientes
7	fila_espera	Lista de espera para horários lotados
8	comissao	Cálculo de comissão por barbeiro (avulso e plano)
9	notificacoes	Notificações por SMS/WhatsApp/e-mail
10	pix_integrado	Pagamento PIX com comprovante e aprovação manual
\.


--
-- Data for Name: fila_espera; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.fila_espera (id, barbearia_id, cliente_id, barbeiro_preferido_id, servico_id, data_preferida, prioridade, posicao, status, chamado_em, criado_em) FROM stdin;
\.


--
-- Data for Name: horarios_bloqueados; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.horarios_bloqueados (id, barbeiro_id, data_hora_inicio, data_hora_fim, motivo, barbearia_id) FROM stdin;
\.


--
-- Data for Name: notificacoes; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notificacoes (id, barbearia_id, usuario_id, agendamento_id, tipo, canal, titulo, corpo, lida, enviada, criado_em) FROM stdin;
1	1	4	7	lembrete_barbeiro	in_app	Próximo agendamento	alceno chega em 15 minutos (11:00).	f	t	2026-06-30 06:43:42.965714
2	1	8	11	lembrete_cliente	in_app	Lembrete de agendamento	Seu agendamento de sobrancelha começa em 30 minutos (11:49).	f	t	2026-06-30 10:18:13.547193
3	1	4	11	lembrete_barbeiro	in_app	Próximo agendamento	QA Cliente Cutoff chega em 15 minutos (11:49).	f	t	2026-06-30 10:33:13.549684
4	1	4	6	lembrete_barbeiro	in_app	Próximo agendamento	alceno chega em 15 minutos (15:30).	f	t	2026-06-30 14:13:47.040033
\.


--
-- Data for Name: pagamentos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pagamentos (id, atendimento_id, forma_pagamento, valor, status, gateway, gateway_transaction_id, criado_em, gateway_status, gateway_metadata) FROM stdin;
\.


--
-- Data for Name: pausa_barbeiro; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pausa_barbeiro (id, barbearia_id, barbeiro_id, hora_inicio, hora_fim, descricao, criado_em) FROM stdin;
1	1	1	12:00:00	13:00:00	almoço	2026-06-29 16:30:56.889002
\.


--
-- Data for Name: plano_barbeiros; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.plano_barbeiros (id, plano_id, barbeiro_id, barbearia_id, adicionado_em) FROM stdin;
\.


--
-- Data for Name: plano_servicos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.plano_servicos (id, plano_id, servico_id, limite_uso_mensal, dias_expiracao, ativo) FROM stdin;
1	1	2	2	30	t
2	1	1	4	30	t
3	2	2	4	30	t
4	2	1	4	30	t
5	2	3	4	30	t
6	3	2	4	30	t
7	3	1	4	30	t
8	3	3	99999	30	t
9	4	2	2	15	t
10	4	1	2	15	t
11	4	3	1	15	t
13	3	4	1	30	t
\.


--
-- Data for Name: planos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.planos (id, barbeiro_id, nome, descricao, preco_mensal, ativo, criado_em, atualizado_em, trial_dias, max_assinaturas, barbearia_id) FROM stdin;
4	\N	Plano Médio	Corte + Barba + Sobrancelha	100.00	t	2026-06-29 20:01:51.711691	2026-06-29 20:01:51.711695	0	\N	1
5	\N	Plano Teste TryCatch	editado	49.90	f	2026-06-30 12:20:16.071184	2026-06-30 12:20:16.133555	0	\N	1
3	\N	completo	compelto	400.00	t	2026-06-29 16:45:12.474471	2026-06-30 12:30:42.709544	0	\N	1
1	\N	Vip - 1	\N	150.00	t	2026-06-29 13:32:30.659221	2026-06-30 12:30:59.935497	0	\N	1
2	\N	pacote completo	Corte + Barba + Sobrancelha.	200.00	f	2026-06-29 16:32:17.710396	2026-06-30 12:31:17.293914	0	\N	1
\.


--
-- Data for Name: produtos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.produtos (id, nome, categoria, preco, quantidade_estoque, quantidade_reservada, foto, ativo, criado_em, barbearia_id) FROM stdin;
1	coca	bebida	5.00	3	0	\N	t	2026-06-29 19:51:13.85161	1
2	guarana	bebida	5.00	5	0	\N	t	2026-06-29 19:51:30.92879	1
3	Pomada FOX	pomada	40.00	1	0	\N	t	2026-06-29 19:59:29.095796	1
\.


--
-- Data for Name: reservas_produtos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.reservas_produtos (id, agendamento_id, produto_id, quantidade, status) FROM stdin;
\.


--
-- Data for Name: segmento_rotulos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.segmento_rotulos (id, segmento_id, rotulo_tenant, rotulo_tenant_plural, rotulo_profissional, rotulo_profissional_plural, rotulo_servico, rotulo_servico_plural, rotulo_agendamento, rotulo_agendamento_plural, rotulo_cliente, rotulo_cliente_plural, rotulo_produto, rotulo_produto_plural, rotulo_plano, rotulo_plano_plural, rotulo_pagamento, rotulo_faturamento, rotulo_relatorio, atualizado_em) FROM stdin;
1	1	Barbearia	Barbearias	Barbeiro	Barbeiros	Serviço	Serviços	Agendamento	Agendamentos	Cliente	Clientes	Produto	Produtos	Plano	Planos	Pagamento	Faturamento	Relatório	2026-06-29 17:57:07.545961
2	2	Salão	Salões	Cabeleireira	Cabeleireiras	Tratamento	Tratamentos	Sessão	Sessões	Cliente	Clientes	Produto	Produtos	Pacote	Pacotes	Pagamento	Faturamento	Relatório	2026-06-29 17:57:07.552395
3	3	Ateliê	Ateliês	Manicure	Manicures	Design	Designs	Sessão	Sessões	Cliente	Clientes	Material	Materiais	Pacote	Pacotes	Pagamento	Faturamento	Relatório	2026-06-29 17:57:07.55603
4	4	Clínica	Clínicas	Médico	Médicos	Procedimento	Procedimentos	Consulta	Consultas	Paciente	Pacientes	Medicamento	Medicamentos	Programa	Programas	Pagamento	Faturamento	Relatório	2026-06-29 17:57:07.560849
\.


--
-- Data for Name: segmentos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.segmentos (id, nome, chave) FROM stdin;
1	Barbearia	barbearia
2	Salão de Beleza	salao
3	Nail Art / Manicure	manicure
4	Clínica	clinica
\.


--
-- Data for Name: servicos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.servicos (id, nome, descricao, duracao_minutos, preco, foto, ativo, barbearia_id) FROM stdin;
1	Corte Degrade	\N	45	40.00	\N	t	1
2	Barbar	\N	20	30.00	\N	t	1
3	sobrancelha	\N	20	20.00	\N	t	1
4	Luzes	Luzes de led	240	115.00	\N	t	1
\.


--
-- Data for Name: solicitacoes_liberacao; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.solicitacoes_liberacao (id, barbeiro_id, data, hora_inicio, hora_fim, motivo, status, notificado, data_solicitacao, data_resposta, barbearia_id) FROM stdin;
\.


--
-- Data for Name: solicitacoes_senha; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.solicitacoes_senha (id, usuario_id, barbearia_id, status, criado_em) FROM stdin;
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.usuarios (id, barbearia_id, nome, telefone, email, senha, perfil, ativo, foto_perfil_url, data_nascimento, criado_em, duplo_fator_ativo, duplo_fator_segredo, whatsapp_verificado) FROM stdin;
1	\N	Super Admin	11999999999	adm@barbearia.com	scrypt:32768:8:1$Olvyf7aG97SmdJh4$f1cb23fb28917ffea02a576cb40f42ec4b74d44027ceedc0415de87e434a9c667a909cb2dde357ed4391df7ddebe75e3e1c24f89433f756d1f8d3d6f728a9317	super_admin	t	\N	\N	2026-06-29 02:18:01.675123	f	\N	f
2	1	Winner Granvile	69999999999	winner@gestor.com	scrypt:32768:8:1$ynECKD5CQem7JWtm$28fa529cec3997f50ed1bf4cf0a2de090faa6ddc0af3501d1f4e213d262c98f4fc0caf2558e94a51d14412009763eb3983b5533e80e754aba123ff7ed3d7969c	gestor	t	\N	\N	2026-06-29 02:21:56.495524	f	\N	f
3	2	Gestor Teste	11999990001	gestor.teste@barbearia-auto.com	scrypt:32768:8:1$oBA4cSKht1MpDZwv$8a4802c6a3a697588c582b6dd25e0fe78467a682e7928ea3dbae66917ebb86c3cbd6ec9feb44e5d07ff7777009282bc5759d27cd8b97943198d4109acd9ef6f2	gestor	t	\N	\N	2026-06-29 03:45:16.64513	f	\N	f
4	1	Winner Granville	69999999999	winner@barber.com	scrypt:32768:8:1$I9KrRhYZLwlcmSZ8$186862f78cb51c679a5bf0adc4c2b47d5c0a4e9705058ada20cb813def2b53bdc1ed272a13fc2d0ed177821bc1c4847236fa011c5536175ba2859c4618ba5c7f	barbeiro	t	\N	\N	2026-06-29 13:27:16.715166	f	\N	f
5	3	teste1	69998765432	teste1@gestor.com	scrypt:32768:8:1$xHJMa6SEFlY5h7oe$7f71c73fc0b1b3e9890936b2395325337876c4b0eddef791872bf64b03a6b34d4415ee10405ce2723d9afa227a068303f891ab996923c825cf63ab6c7dfaa89e	gestor	t	\N	\N	2026-06-29 19:13:17.348448	f	\N	f
7	1	QA Cliente Smoke	11900005678	\N	scrypt:32768:8:1$M9XcB39KqgEU7JTg$01502212657d6b2578ec8727390ffa25f7534da4e173a71ed35f443603cf0f774a19b0e1166a1f96284c19b02e4ac8ddb6286f88a1ac0fd22a9cecdd3ac2434f	cliente	t	\N	\N	2026-06-30 09:46:31.419321	f	\N	f
8	1	QA Cliente Cutoff	11900009999	qa.cutoff@teste.com	scrypt:32768:8:1$guomIpebeR39bWtk$c61ba2c5840f3654a2dc9dae0be61e09981fc2ded26adbc37417d74f54bcae2611ebe771303938772c4581d1f2a946138a34e78332a644b5b37933a3c3ad6d61	cliente	t	\N	\N	2026-06-30 09:48:59.209844	f	\N	f
9	1	alceno aguiar	69993921709	idprimeweb01@gmail.com	scrypt:32768:8:1$uHXfBN6VUA3DQnvs$2445f1bf8c81f4e6cab4b605adea11c960a0de4e2b0a3aa118f46d808c827dfdaf67f327607c899ea9a0ce6ab14055c4f9d81dedea8ecd856eb9da4a5ba672e4	cliente	t	\N	\N	2026-06-30 12:34:13.730174	f	\N	f
10	1	teste1	69998765431	teste1@cliente.com	scrypt:32768:8:1$kHpW7LCtmdEl12ub$1e0fe9f5480c3995aeda55f0e37b1bed337af4185fca2300e9a95ee5cd4c449e06331100ee723a50194ef2f338127e0e60b600803d9fa90cdf0eb9e2865c4c38	cliente	t	\N	\N	2026-06-30 12:40:06.088775	f	\N	f
\.


--
-- Data for Name: vip_niveis; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.vip_niveis (id, nivel, brinde_descricao, tipo_brinde, valor_desconto, ativo, modo_brinde_ativo, criado_em, barbearia_id) FROM stdin;
\.


--
-- Name: agendamento_servicos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.agendamento_servicos_id_seq', 19, true);


--
-- Name: agendamento_solicitacao_pix_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.agendamento_solicitacao_pix_id_seq', 7, true);


--
-- Name: agendamentos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.agendamentos_id_seq', 15, true);


--
-- Name: atendimento_itens_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.atendimento_itens_id_seq', 1, false);


--
-- Name: atendimentos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.atendimentos_id_seq', 1, false);


--
-- Name: auditoria_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auditoria_log_id_seq', 1, false);


--
-- Name: barbearia_customizacao_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.barbearia_customizacao_id_seq', 3, true);


--
-- Name: barbearias_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.barbearias_id_seq', 3, true);


--
-- Name: barbeiro_comissao_servico_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.barbeiro_comissao_servico_id_seq', 1, false);


--
-- Name: barbeiro_servicos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.barbeiro_servicos_id_seq', 4, true);


--
-- Name: barbeiros_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.barbeiros_id_seq', 1, true);


--
-- Name: cliente_notas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cliente_notas_id_seq', 2, true);


--
-- Name: cliente_plano_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cliente_plano_id_seq', 1, false);


--
-- Name: cliente_plano_solicitacao_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cliente_plano_solicitacao_id_seq', 1, true);


--
-- Name: cliente_plano_uso_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cliente_plano_uso_id_seq', 1, false);


--
-- Name: cliente_vip_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cliente_vip_id_seq', 1, false);


--
-- Name: clientes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.clientes_id_seq', 13, true);


--
-- Name: configuracao_agenda_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.configuracao_agenda_id_seq', 1, true);


--
-- Name: configuracao_agendamento_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.configuracao_agendamento_id_seq', 3, true);


--
-- Name: cupons_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cupons_id_seq', 3, true);


--
-- Name: feature_barbearia_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.feature_barbearia_id_seq', 21, true);


--
-- Name: feature_metadata_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.feature_metadata_id_seq', 10, true);


--
-- Name: fila_espera_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.fila_espera_id_seq', 1, false);


--
-- Name: horarios_bloqueados_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.horarios_bloqueados_id_seq', 1, false);


--
-- Name: notificacoes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.notificacoes_id_seq', 4, true);


--
-- Name: pagamentos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.pagamentos_id_seq', 1, false);


--
-- Name: pausa_barbeiro_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.pausa_barbeiro_id_seq', 2, true);


--
-- Name: plano_barbeiros_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.plano_barbeiros_id_seq', 1, false);


--
-- Name: plano_servicos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.plano_servicos_id_seq', 13, true);


--
-- Name: planos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.planos_id_seq', 5, true);


--
-- Name: produtos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.produtos_id_seq', 3, true);


--
-- Name: reservas_produtos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.reservas_produtos_id_seq', 1, false);


--
-- Name: segmento_rotulos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.segmento_rotulos_id_seq', 4, true);


--
-- Name: segmentos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.segmentos_id_seq', 4, true);


--
-- Name: servicos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.servicos_id_seq', 4, true);


--
-- Name: solicitacoes_liberacao_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.solicitacoes_liberacao_id_seq', 1, false);


--
-- Name: solicitacoes_senha_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.solicitacoes_senha_id_seq', 1, false);


--
-- Name: usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.usuarios_id_seq', 10, true);


--
-- Name: vip_niveis_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.vip_niveis_id_seq', 1, false);


--
-- Name: agendamento_servicos agendamento_servicos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_servicos
    ADD CONSTRAINT agendamento_servicos_pkey PRIMARY KEY (id);


--
-- Name: agendamento_solicitacao_pix agendamento_solicitacao_pix_agendamento_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_solicitacao_pix
    ADD CONSTRAINT agendamento_solicitacao_pix_agendamento_id_key UNIQUE (agendamento_id);


--
-- Name: agendamento_solicitacao_pix agendamento_solicitacao_pix_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_solicitacao_pix
    ADD CONSTRAINT agendamento_solicitacao_pix_pkey PRIMARY KEY (id);


--
-- Name: agendamentos agendamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamentos
    ADD CONSTRAINT agendamentos_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: atendimento_itens atendimento_itens_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimento_itens
    ADD CONSTRAINT atendimento_itens_pkey PRIMARY KEY (id);


--
-- Name: atendimentos atendimentos_agendamento_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos
    ADD CONSTRAINT atendimentos_agendamento_id_key UNIQUE (agendamento_id);


--
-- Name: atendimentos atendimentos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos
    ADD CONSTRAINT atendimentos_pkey PRIMARY KEY (id);


--
-- Name: auditoria_log auditoria_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auditoria_log
    ADD CONSTRAINT auditoria_log_pkey PRIMARY KEY (id);


--
-- Name: barbearia_customizacao barbearia_customizacao_barbearia_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearia_customizacao
    ADD CONSTRAINT barbearia_customizacao_barbearia_id_key UNIQUE (barbearia_id);


--
-- Name: barbearia_customizacao barbearia_customizacao_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearia_customizacao
    ADD CONSTRAINT barbearia_customizacao_pkey PRIMARY KEY (id);


--
-- Name: barbearias barbearias_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearias
    ADD CONSTRAINT barbearias_pkey PRIMARY KEY (id);


--
-- Name: barbeiro_comissao_servico barbeiro_comissao_servico_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_comissao_servico
    ADD CONSTRAINT barbeiro_comissao_servico_pkey PRIMARY KEY (id);


--
-- Name: barbeiro_servicos barbeiro_servicos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_servicos
    ADD CONSTRAINT barbeiro_servicos_pkey PRIMARY KEY (id);


--
-- Name: barbeiros barbeiros_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiros
    ADD CONSTRAINT barbeiros_pkey PRIMARY KEY (id);


--
-- Name: cliente_notas cliente_notas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_notas
    ADD CONSTRAINT cliente_notas_pkey PRIMARY KEY (id);


--
-- Name: cliente_plano cliente_plano_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano
    ADD CONSTRAINT cliente_plano_pkey PRIMARY KEY (id);


--
-- Name: cliente_plano_solicitacao cliente_plano_solicitacao_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_solicitacao
    ADD CONSTRAINT cliente_plano_solicitacao_pkey PRIMARY KEY (id);


--
-- Name: cliente_plano_uso cliente_plano_uso_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_uso
    ADD CONSTRAINT cliente_plano_uso_pkey PRIMARY KEY (id);


--
-- Name: cliente_vip cliente_vip_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_vip
    ADD CONSTRAINT cliente_vip_pkey PRIMARY KEY (id);


--
-- Name: clientes clientes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_pkey PRIMARY KEY (id);


--
-- Name: configuracao_agenda configuracao_agenda_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agenda
    ADD CONSTRAINT configuracao_agenda_pkey PRIMARY KEY (id);


--
-- Name: configuracao_agendamento configuracao_agendamento_barbearia_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agendamento
    ADD CONSTRAINT configuracao_agendamento_barbearia_id_key UNIQUE (barbearia_id);


--
-- Name: configuracao_agendamento configuracao_agendamento_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agendamento
    ADD CONSTRAINT configuracao_agendamento_pkey PRIMARY KEY (id);


--
-- Name: cupons cupons_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cupons
    ADD CONSTRAINT cupons_pkey PRIMARY KEY (id);


--
-- Name: feature_barbearia feature_barbearia_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_barbearia
    ADD CONSTRAINT feature_barbearia_pkey PRIMARY KEY (id);


--
-- Name: feature_metadata feature_metadata_nome_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_metadata
    ADD CONSTRAINT feature_metadata_nome_key UNIQUE (nome);


--
-- Name: feature_metadata feature_metadata_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_metadata
    ADD CONSTRAINT feature_metadata_pkey PRIMARY KEY (id);


--
-- Name: fila_espera fila_espera_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fila_espera
    ADD CONSTRAINT fila_espera_pkey PRIMARY KEY (id);


--
-- Name: horarios_bloqueados horarios_bloqueados_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.horarios_bloqueados
    ADD CONSTRAINT horarios_bloqueados_pkey PRIMARY KEY (id);


--
-- Name: notificacoes notificacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificacoes
    ADD CONSTRAINT notificacoes_pkey PRIMARY KEY (id);


--
-- Name: pagamentos pagamentos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pagamentos
    ADD CONSTRAINT pagamentos_pkey PRIMARY KEY (id);


--
-- Name: pausa_barbeiro pausa_barbeiro_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pausa_barbeiro
    ADD CONSTRAINT pausa_barbeiro_pkey PRIMARY KEY (id);


--
-- Name: plano_barbeiros plano_barbeiros_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_barbeiros
    ADD CONSTRAINT plano_barbeiros_pkey PRIMARY KEY (id);


--
-- Name: plano_servicos plano_servicos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_servicos
    ADD CONSTRAINT plano_servicos_pkey PRIMARY KEY (id);


--
-- Name: planos planos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planos
    ADD CONSTRAINT planos_pkey PRIMARY KEY (id);


--
-- Name: produtos produtos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.produtos
    ADD CONSTRAINT produtos_pkey PRIMARY KEY (id);


--
-- Name: reservas_produtos reservas_produtos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservas_produtos
    ADD CONSTRAINT reservas_produtos_pkey PRIMARY KEY (id);


--
-- Name: segmento_rotulos segmento_rotulos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmento_rotulos
    ADD CONSTRAINT segmento_rotulos_pkey PRIMARY KEY (id);


--
-- Name: segmento_rotulos segmento_rotulos_segmento_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmento_rotulos
    ADD CONSTRAINT segmento_rotulos_segmento_id_key UNIQUE (segmento_id);


--
-- Name: segmentos segmentos_chave_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmentos
    ADD CONSTRAINT segmentos_chave_key UNIQUE (chave);


--
-- Name: segmentos segmentos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmentos
    ADD CONSTRAINT segmentos_pkey PRIMARY KEY (id);


--
-- Name: servicos servicos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servicos
    ADD CONSTRAINT servicos_pkey PRIMARY KEY (id);


--
-- Name: solicitacoes_liberacao solicitacoes_liberacao_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_liberacao
    ADD CONSTRAINT solicitacoes_liberacao_pkey PRIMARY KEY (id);


--
-- Name: solicitacoes_senha solicitacoes_senha_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_senha
    ADD CONSTRAINT solicitacoes_senha_pkey PRIMARY KEY (id);


--
-- Name: vip_niveis uq_barbearia_nivel; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vip_niveis
    ADD CONSTRAINT uq_barbearia_nivel UNIQUE (barbearia_id, nivel);


--
-- Name: barbeiro_servicos uq_barbeiro_servico; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_servicos
    ADD CONSTRAINT uq_barbeiro_servico UNIQUE (barbeiro_id, servico_id);


--
-- Name: clientes uq_cliente_barbearia_telefone; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT uq_cliente_barbearia_telefone UNIQUE (barbearia_id, telefone);


--
-- Name: cliente_vip uq_cliente_barbearia_vip; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_vip
    ADD CONSTRAINT uq_cliente_barbearia_vip UNIQUE (cliente_id, barbearia_id);


--
-- Name: barbeiro_comissao_servico uq_comissao_barbeiro_servico; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_comissao_servico
    ADD CONSTRAINT uq_comissao_barbeiro_servico UNIQUE (barbeiro_id, servico_id);


--
-- Name: configuracao_agenda uq_configuracao_agenda_barbeiro; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agenda
    ADD CONSTRAINT uq_configuracao_agenda_barbeiro UNIQUE (barbeiro_id);


--
-- Name: cupons uq_cupom_barbearia_codigo; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cupons
    ADD CONSTRAINT uq_cupom_barbearia_codigo UNIQUE (barbearia_id, codigo);


--
-- Name: feature_barbearia uq_feature_barbearia; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_barbearia
    ADD CONSTRAINT uq_feature_barbearia UNIQUE (barbearia_id, feature_id);


--
-- Name: plano_barbeiros uq_plano_barbeiro; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_barbeiros
    ADD CONSTRAINT uq_plano_barbeiro UNIQUE (plano_id, barbeiro_id);


--
-- Name: plano_servicos uq_plano_servico; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_servicos
    ADD CONSTRAINT uq_plano_servico UNIQUE (plano_id, servico_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: vip_niveis vip_niveis_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vip_niveis
    ADD CONSTRAINT vip_niveis_pkey PRIMARY KEY (id);


--
-- Name: ix_agendamento_servicos_agendamento_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_agendamento_servicos_agendamento_id ON public.agendamento_servicos USING btree (agendamento_id);


--
-- Name: ix_agendamento_solicitacao_pix_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_agendamento_solicitacao_pix_barbearia_id ON public.agendamento_solicitacao_pix USING btree (barbearia_id);


--
-- Name: ix_agendamentos_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_agendamentos_barbearia_id ON public.agendamentos USING btree (barbearia_id);


--
-- Name: ix_agendamentos_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_agendamentos_barbeiro_id ON public.agendamentos USING btree (barbeiro_id);


--
-- Name: ix_agendamentos_cliente_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_agendamentos_cliente_id ON public.agendamentos USING btree (cliente_id);


--
-- Name: ix_atendimento_itens_atendimento_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_atendimento_itens_atendimento_id ON public.atendimento_itens USING btree (atendimento_id);


--
-- Name: ix_atendimentos_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_atendimentos_barbearia_id ON public.atendimentos USING btree (barbearia_id);


--
-- Name: ix_atendimentos_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_atendimentos_barbeiro_id ON public.atendimentos USING btree (barbeiro_id);


--
-- Name: ix_barbearias_slug; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_barbearias_slug ON public.barbearias USING btree (slug);


--
-- Name: ix_barbeiro_comissao_servico_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_barbeiro_comissao_servico_barbearia_id ON public.barbeiro_comissao_servico USING btree (barbearia_id);


--
-- Name: ix_barbeiro_comissao_servico_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_barbeiro_comissao_servico_barbeiro_id ON public.barbeiro_comissao_servico USING btree (barbeiro_id);


--
-- Name: ix_barbeiro_servicos_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_barbeiro_servicos_barbeiro_id ON public.barbeiro_servicos USING btree (barbeiro_id);


--
-- Name: ix_barbeiros_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_barbeiros_barbearia_id ON public.barbeiros USING btree (barbearia_id);


--
-- Name: ix_cliente_notas_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_notas_barbearia_id ON public.cliente_notas USING btree (barbearia_id);


--
-- Name: ix_cliente_notas_cliente_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_notas_cliente_id ON public.cliente_notas USING btree (cliente_id);


--
-- Name: ix_cliente_plano_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_plano_barbearia_id ON public.cliente_plano USING btree (barbearia_id);


--
-- Name: ix_cliente_plano_cliente_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_plano_cliente_id ON public.cliente_plano USING btree (cliente_id);


--
-- Name: ix_cliente_plano_solicitacao_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_plano_solicitacao_barbearia_id ON public.cliente_plano_solicitacao USING btree (barbearia_id);


--
-- Name: ix_cliente_plano_uso_cliente_plano_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_plano_uso_cliente_plano_id ON public.cliente_plano_uso USING btree (cliente_plano_id);


--
-- Name: ix_cliente_vip_cliente_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cliente_vip_cliente_id ON public.cliente_vip USING btree (cliente_id);


--
-- Name: ix_clientes_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_clientes_barbearia_id ON public.clientes USING btree (barbearia_id);


--
-- Name: ix_configuracao_agenda_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_configuracao_agenda_barbearia_id ON public.configuracao_agenda USING btree (barbearia_id);


--
-- Name: ix_cupons_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_cupons_barbearia_id ON public.cupons USING btree (barbearia_id);


--
-- Name: ix_feature_barbearia_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_feature_barbearia_barbearia_id ON public.feature_barbearia USING btree (barbearia_id);


--
-- Name: ix_fila_espera_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fila_espera_barbearia_id ON public.fila_espera USING btree (barbearia_id);


--
-- Name: ix_fila_espera_cliente_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_fila_espera_cliente_id ON public.fila_espera USING btree (cliente_id);


--
-- Name: ix_horarios_bloqueados_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_horarios_bloqueados_barbearia_id ON public.horarios_bloqueados USING btree (barbearia_id);


--
-- Name: ix_horarios_bloqueados_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_horarios_bloqueados_barbeiro_id ON public.horarios_bloqueados USING btree (barbeiro_id);


--
-- Name: ix_notificacoes_agendamento_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notificacoes_agendamento_id ON public.notificacoes USING btree (agendamento_id);


--
-- Name: ix_notificacoes_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notificacoes_barbearia_id ON public.notificacoes USING btree (barbearia_id);


--
-- Name: ix_notificacoes_usuario_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notificacoes_usuario_id ON public.notificacoes USING btree (usuario_id);


--
-- Name: ix_pagamentos_atendimento_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_pagamentos_atendimento_id ON public.pagamentos USING btree (atendimento_id);


--
-- Name: ix_pausa_barbeiro_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_pausa_barbeiro_barbeiro_id ON public.pausa_barbeiro USING btree (barbeiro_id);


--
-- Name: ix_plano_barbeiros_plano_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_plano_barbeiros_plano_id ON public.plano_barbeiros USING btree (plano_id);


--
-- Name: ix_plano_servicos_plano_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_plano_servicos_plano_id ON public.plano_servicos USING btree (plano_id);


--
-- Name: ix_planos_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_planos_barbearia_id ON public.planos USING btree (barbearia_id);


--
-- Name: ix_produtos_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_produtos_barbearia_id ON public.produtos USING btree (barbearia_id);


--
-- Name: ix_reservas_produtos_agendamento_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_reservas_produtos_agendamento_id ON public.reservas_produtos USING btree (agendamento_id);


--
-- Name: ix_segmentos_chave; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_segmentos_chave ON public.segmentos USING btree (chave);


--
-- Name: ix_servicos_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_servicos_barbearia_id ON public.servicos USING btree (barbearia_id);


--
-- Name: ix_solicitacoes_liberacao_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_solicitacoes_liberacao_barbearia_id ON public.solicitacoes_liberacao USING btree (barbearia_id);


--
-- Name: ix_solicitacoes_liberacao_barbeiro_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_solicitacoes_liberacao_barbeiro_id ON public.solicitacoes_liberacao USING btree (barbeiro_id);


--
-- Name: ix_usuarios_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_usuarios_barbearia_id ON public.usuarios USING btree (barbearia_id);


--
-- Name: ix_vip_niveis_barbearia_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_vip_niveis_barbearia_id ON public.vip_niveis USING btree (barbearia_id);


--
-- Name: agendamento_servicos agendamento_servicos_agendamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_servicos
    ADD CONSTRAINT agendamento_servicos_agendamento_id_fkey FOREIGN KEY (agendamento_id) REFERENCES public.agendamentos(id);


--
-- Name: agendamento_servicos agendamento_servicos_cliente_plano_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_servicos
    ADD CONSTRAINT agendamento_servicos_cliente_plano_id_fkey FOREIGN KEY (cliente_plano_id) REFERENCES public.cliente_plano(id);


--
-- Name: agendamento_servicos agendamento_servicos_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_servicos
    ADD CONSTRAINT agendamento_servicos_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: agendamento_solicitacao_pix agendamento_solicitacao_pix_agendamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_solicitacao_pix
    ADD CONSTRAINT agendamento_solicitacao_pix_agendamento_id_fkey FOREIGN KEY (agendamento_id) REFERENCES public.agendamentos(id);


--
-- Name: agendamento_solicitacao_pix agendamento_solicitacao_pix_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamento_solicitacao_pix
    ADD CONSTRAINT agendamento_solicitacao_pix_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: agendamentos agendamentos_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamentos
    ADD CONSTRAINT agendamentos_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: agendamentos agendamentos_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamentos
    ADD CONSTRAINT agendamentos_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: agendamentos agendamentos_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamentos
    ADD CONSTRAINT agendamentos_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: atendimento_itens atendimento_itens_atendimento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimento_itens
    ADD CONSTRAINT atendimento_itens_atendimento_id_fkey FOREIGN KEY (atendimento_id) REFERENCES public.atendimentos(id);


--
-- Name: atendimento_itens atendimento_itens_produto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimento_itens
    ADD CONSTRAINT atendimento_itens_produto_id_fkey FOREIGN KEY (produto_id) REFERENCES public.produtos(id);


--
-- Name: atendimento_itens atendimento_itens_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimento_itens
    ADD CONSTRAINT atendimento_itens_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: atendimentos atendimentos_agendamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos
    ADD CONSTRAINT atendimentos_agendamento_id_fkey FOREIGN KEY (agendamento_id) REFERENCES public.agendamentos(id);


--
-- Name: atendimentos atendimentos_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos
    ADD CONSTRAINT atendimentos_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: atendimentos atendimentos_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos
    ADD CONSTRAINT atendimentos_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: atendimentos atendimentos_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.atendimentos
    ADD CONSTRAINT atendimentos_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: auditoria_log auditoria_log_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auditoria_log
    ADD CONSTRAINT auditoria_log_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: auditoria_log auditoria_log_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auditoria_log
    ADD CONSTRAINT auditoria_log_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: barbearia_customizacao barbearia_customizacao_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearia_customizacao
    ADD CONSTRAINT barbearia_customizacao_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: barbeiro_comissao_servico barbeiro_comissao_servico_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_comissao_servico
    ADD CONSTRAINT barbeiro_comissao_servico_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: barbeiro_comissao_servico barbeiro_comissao_servico_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_comissao_servico
    ADD CONSTRAINT barbeiro_comissao_servico_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: barbeiro_comissao_servico barbeiro_comissao_servico_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_comissao_servico
    ADD CONSTRAINT barbeiro_comissao_servico_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: barbeiro_servicos barbeiro_servicos_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_servicos
    ADD CONSTRAINT barbeiro_servicos_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: barbeiro_servicos barbeiro_servicos_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiro_servicos
    ADD CONSTRAINT barbeiro_servicos_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: barbeiros barbeiros_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiros
    ADD CONSTRAINT barbeiros_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: barbeiros barbeiros_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbeiros
    ADD CONSTRAINT barbeiros_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: cliente_notas cliente_notas_autor_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_notas
    ADD CONSTRAINT cliente_notas_autor_usuario_id_fkey FOREIGN KEY (autor_usuario_id) REFERENCES public.usuarios(id);


--
-- Name: cliente_notas cliente_notas_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_notas
    ADD CONSTRAINT cliente_notas_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: cliente_notas cliente_notas_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_notas
    ADD CONSTRAINT cliente_notas_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: cliente_plano cliente_plano_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano
    ADD CONSTRAINT cliente_plano_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: cliente_plano cliente_plano_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano
    ADD CONSTRAINT cliente_plano_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: cliente_plano cliente_plano_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano
    ADD CONSTRAINT cliente_plano_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: cliente_plano cliente_plano_plano_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano
    ADD CONSTRAINT cliente_plano_plano_id_fkey FOREIGN KEY (plano_id) REFERENCES public.planos(id);


--
-- Name: cliente_plano_solicitacao cliente_plano_solicitacao_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_solicitacao
    ADD CONSTRAINT cliente_plano_solicitacao_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: cliente_plano_solicitacao cliente_plano_solicitacao_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_solicitacao
    ADD CONSTRAINT cliente_plano_solicitacao_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: cliente_plano_solicitacao cliente_plano_solicitacao_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_solicitacao
    ADD CONSTRAINT cliente_plano_solicitacao_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: cliente_plano_solicitacao cliente_plano_solicitacao_plano_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_solicitacao
    ADD CONSTRAINT cliente_plano_solicitacao_plano_id_fkey FOREIGN KEY (plano_id) REFERENCES public.planos(id);


--
-- Name: cliente_plano_uso cliente_plano_uso_cliente_plano_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_uso
    ADD CONSTRAINT cliente_plano_uso_cliente_plano_id_fkey FOREIGN KEY (cliente_plano_id) REFERENCES public.cliente_plano(id);


--
-- Name: cliente_plano_uso cliente_plano_uso_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_plano_uso
    ADD CONSTRAINT cliente_plano_uso_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: cliente_vip cliente_vip_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_vip
    ADD CONSTRAINT cliente_vip_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: cliente_vip cliente_vip_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente_vip
    ADD CONSTRAINT cliente_vip_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: clientes clientes_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: clientes clientes_barbeiro_preferido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_barbeiro_preferido_id_fkey FOREIGN KEY (barbeiro_preferido_id) REFERENCES public.barbeiros(id);


--
-- Name: clientes clientes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.clientes
    ADD CONSTRAINT clientes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: configuracao_agenda configuracao_agenda_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agenda
    ADD CONSTRAINT configuracao_agenda_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: configuracao_agenda configuracao_agenda_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agenda
    ADD CONSTRAINT configuracao_agenda_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: configuracao_agendamento configuracao_agendamento_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.configuracao_agendamento
    ADD CONSTRAINT configuracao_agendamento_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: cupons cupons_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cupons
    ADD CONSTRAINT cupons_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: feature_barbearia feature_barbearia_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_barbearia
    ADD CONSTRAINT feature_barbearia_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: feature_barbearia feature_barbearia_feature_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.feature_barbearia
    ADD CONSTRAINT feature_barbearia_feature_id_fkey FOREIGN KEY (feature_id) REFERENCES public.feature_metadata(id);


--
-- Name: fila_espera fila_espera_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fila_espera
    ADD CONSTRAINT fila_espera_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: fila_espera fila_espera_barbeiro_preferido_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fila_espera
    ADD CONSTRAINT fila_espera_barbeiro_preferido_id_fkey FOREIGN KEY (barbeiro_preferido_id) REFERENCES public.barbeiros(id);


--
-- Name: fila_espera fila_espera_cliente_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fila_espera
    ADD CONSTRAINT fila_espera_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES public.clientes(id);


--
-- Name: fila_espera fila_espera_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fila_espera
    ADD CONSTRAINT fila_espera_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: agendamentos fk_agendamentos_cupom_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.agendamentos
    ADD CONSTRAINT fk_agendamentos_cupom_id FOREIGN KEY (cupom_id) REFERENCES public.cupons(id);


--
-- Name: barbearias fk_barbearias_segmento_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.barbearias
    ADD CONSTRAINT fk_barbearias_segmento_id FOREIGN KEY (segmento_id) REFERENCES public.segmentos(id);


--
-- Name: horarios_bloqueados horarios_bloqueados_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.horarios_bloqueados
    ADD CONSTRAINT horarios_bloqueados_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: horarios_bloqueados horarios_bloqueados_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.horarios_bloqueados
    ADD CONSTRAINT horarios_bloqueados_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: notificacoes notificacoes_agendamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificacoes
    ADD CONSTRAINT notificacoes_agendamento_id_fkey FOREIGN KEY (agendamento_id) REFERENCES public.agendamentos(id);


--
-- Name: notificacoes notificacoes_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificacoes
    ADD CONSTRAINT notificacoes_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: notificacoes notificacoes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notificacoes
    ADD CONSTRAINT notificacoes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: pagamentos pagamentos_atendimento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pagamentos
    ADD CONSTRAINT pagamentos_atendimento_id_fkey FOREIGN KEY (atendimento_id) REFERENCES public.atendimentos(id);


--
-- Name: pausa_barbeiro pausa_barbeiro_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pausa_barbeiro
    ADD CONSTRAINT pausa_barbeiro_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: pausa_barbeiro pausa_barbeiro_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pausa_barbeiro
    ADD CONSTRAINT pausa_barbeiro_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: plano_barbeiros plano_barbeiros_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_barbeiros
    ADD CONSTRAINT plano_barbeiros_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: plano_barbeiros plano_barbeiros_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_barbeiros
    ADD CONSTRAINT plano_barbeiros_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: plano_barbeiros plano_barbeiros_plano_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_barbeiros
    ADD CONSTRAINT plano_barbeiros_plano_id_fkey FOREIGN KEY (plano_id) REFERENCES public.planos(id);


--
-- Name: plano_servicos plano_servicos_plano_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_servicos
    ADD CONSTRAINT plano_servicos_plano_id_fkey FOREIGN KEY (plano_id) REFERENCES public.planos(id);


--
-- Name: plano_servicos plano_servicos_servico_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.plano_servicos
    ADD CONSTRAINT plano_servicos_servico_id_fkey FOREIGN KEY (servico_id) REFERENCES public.servicos(id);


--
-- Name: planos planos_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planos
    ADD CONSTRAINT planos_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: planos planos_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.planos
    ADD CONSTRAINT planos_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: produtos produtos_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.produtos
    ADD CONSTRAINT produtos_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: reservas_produtos reservas_produtos_agendamento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservas_produtos
    ADD CONSTRAINT reservas_produtos_agendamento_id_fkey FOREIGN KEY (agendamento_id) REFERENCES public.agendamentos(id);


--
-- Name: reservas_produtos reservas_produtos_produto_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.reservas_produtos
    ADD CONSTRAINT reservas_produtos_produto_id_fkey FOREIGN KEY (produto_id) REFERENCES public.produtos(id);


--
-- Name: segmento_rotulos segmento_rotulos_segmento_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.segmento_rotulos
    ADD CONSTRAINT segmento_rotulos_segmento_id_fkey FOREIGN KEY (segmento_id) REFERENCES public.segmentos(id);


--
-- Name: servicos servicos_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.servicos
    ADD CONSTRAINT servicos_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: solicitacoes_liberacao solicitacoes_liberacao_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_liberacao
    ADD CONSTRAINT solicitacoes_liberacao_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: solicitacoes_liberacao solicitacoes_liberacao_barbeiro_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_liberacao
    ADD CONSTRAINT solicitacoes_liberacao_barbeiro_id_fkey FOREIGN KEY (barbeiro_id) REFERENCES public.barbeiros(id);


--
-- Name: solicitacoes_senha solicitacoes_senha_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_senha
    ADD CONSTRAINT solicitacoes_senha_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: solicitacoes_senha solicitacoes_senha_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.solicitacoes_senha
    ADD CONSTRAINT solicitacoes_senha_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id);


--
-- Name: usuarios usuarios_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- Name: vip_niveis vip_niveis_barbearia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vip_niveis
    ADD CONSTRAINT vip_niveis_barbearia_id_fkey FOREIGN KEY (barbearia_id) REFERENCES public.barbearias(id);


--
-- PostgreSQL database dump complete
--

\unrestrict gbj9rHmF5jzWzdfWYtUphKfCi2Fq6JSPrzutilYS2P8RA7JQQ30bOrqIVyagjjn

