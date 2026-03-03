#!/usr/bin/env python3
"""
╔════════════════════════════════════════════════════════════════════════╗
║                    🤖 IA ROUTER v1.0                                  ║
║         Sistema de Roteamento Multi-IA (Maya, Amanda, etc)            ║
║                                                                        ║
║  Como funciona:                                                       ║
║  1. Link no Instagram aponta pra /start?ia=amanda                     ║
║  2. Sistema detecta qual IA baseado no parâmetro                      ║
║  3. Carrega configuração específica da IA                             ║
║  4. Código principal da Maya roda normalmente (ZERO mudanças)         ║
║  5. Respostas, fotos, prompts são específicos de cada IA              ║
╚════════════════════════════════════════════════════════════════════════╝
"""

import json
import redis
import logging
from datetime import date

logger = logging.getLogger(__name__)

class IARouter:
    def __init__(self, config_path="ias_config.json", redis_url=None):
        """Inicializa o roteador com config das IAs"""
        self.config = self._load_config(config_path)
        self.redis_url = redis_url
        self.r = None
        
        if redis_url:
            try:
                self.r = redis.from_url(redis_url, decode_responses=True)
                self.r.ping()
                logger.info("✅ Redis conectado para IA Router")
            except Exception as e:
                logger.error(f"❌ Redis erro: {e}")
    
    def _load_config(self, config_path):
        """Carrega configuração das IAs"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"❌ Config file not found: {config_path}")
            return {"ias": {}, "default_ia": "maya"}
        except Exception as e:
            logger.error(f"❌ Config load error: {e}")
            return {"ias": {}, "default_ia": "maya"}
    
    # ═══════════════════════════════════════════════════════════════════════
    # 🔑 REDIS KEYS - Armazena qual IA cada usuário usa
    # ═══════════════════════════════════════════════════════════════════════
    
    def _assigned_ia_key(self, uid):
        """Chave Redis da IA atribuída ao usuário"""
        return f"assigned_ia:{uid}"
    
    def _ia_channel_key(self, ia_id):
        """Chave para dados agregados da IA"""
        return f"ia_stats:{ia_id}:{date.today()}"
    
    def _user_ia_list_key(self, ia_id):
        """Chave para lista de usuários da IA"""
        return f"ia_users:{ia_id}"
    
    # ═══════════════════════════════════════════════════════════════════════
    # 📌 ATRIBUIÇÃO DE IA
    # ═══════════════════════════════════════════════════════════════════════
    
    def assign_ia(self, uid, ia_id):
        """
        Atribui uma IA a um usuário (geralmente no /start)
        
        Args:
            uid: user ID do Telegram
            ia_id: 'maya', 'amanda', etc
        
        Returns:
            bool: sucesso
        """
        # Valida IA
        if ia_id not in self.config.get("ias", {}):
            logger.warning(f"⚠️ IA desconhecida: {ia_id}. Usando default (maya)")
            ia_id = self.config.get("default_ia", "maya")
        
        # Salva no Redis
        if self.r:
            try:
                self.r.set(self._assigned_ia_key(uid), ia_id)
                self.r.expire(self._assigned_ia_key(uid), 86400 * 365)  # 1 ano
                
                # Adiciona à lista de usuários da IA
                self.r.sadd(self._user_ia_list_key(ia_id), str(uid))
                
                logger.info(f"✅ User {uid} atribuído à IA: {ia_id}")
                return True
            except Exception as e:
                logger.error(f"❌ Erro assign_ia: {e}")
                return False
        else:
            logger.warning("⚠️ Redis não disponível - assign_ia falhou")
            return False
    
    def get_ia(self, uid):
        """
        Retorna a IA atribuída a um usuário
        
        Args:
            uid: user ID do Telegram
        
        Returns:
            str: ia_id (default é 'maya' se não encontrado)
        """
        if self.r:
            try:
                ia_id = self.r.get(self._assigned_ia_key(uid))
                if ia_id:
                    return ia_id
            except Exception as e:
                logger.error(f"❌ Erro get_ia: {e}")
        
        # Fallback: default IA
        default = self.config.get("default_ia", "maya")
        return default
    
    # ═══════════════════════════════════════════════════════════════════════
    # 📋 CARREGAR CONFIGURAÇÃO DE IA
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_ia_config(self, ia_id=None, uid=None):
        """
        Retorna a configuração completa de uma IA
        
        Args:
            ia_id: ID da IA (ou None para usar uid)
            uid: User ID (se ia_id não fornecido)
        
        Returns:
            dict: configuração da IA ou None
        """
        # Se uid fornecido, busca qual IA o usuário usa
        if uid and not ia_id:
            ia_id = self.get_ia(uid)
        
        # Fallback
        if not ia_id:
            ia_id = self.config.get("default_ia", "maya")
        
        # Retorna config
        ia_config = self.config.get("ias", {}).get(ia_id)
        
        if ia_config:
            return ia_config
        else:
            logger.warning(f"⚠️ IA config não encontrada: {ia_id}")
            return None
    
    def get_ia_attribute(self, uid, attr_name, default=None):
        """
        Shortcut: retorna um atributo específico da IA do usuário
        
        Args:
            uid: user ID
            attr_name: 'name', 'preco', 'instagram', etc
            default: valor default se não encontrado
        
        Returns:
            valor do atributo ou default
        """
        ia_config = self.get_ia_config(uid=uid)
        if ia_config:
            return ia_config.get(attr_name, default)
        return default
    
    # ═══════════════════════════════════════════════════════════════════════
    # 📊 ESTATÍSTICAS POR IA
    # ═══════════════════════════════════════════════════════════════════════
    
    def get_ia_stats(self, ia_id):
        """
        Retorna estatísticas de uma IA
        
        Returns:
            dict: {users_count, messages_today, etc}
        """
        if not self.r:
            return {}
        
        try:
            users_key = self._user_ia_list_key(ia_id)
            users_count = self.r.scard(users_key)
            
            # Pode adicionar mais métricas aqui
            return {
                "ia_id": ia_id,
                "users_count": users_count,
                "name": self.get_ia_attribute(None, 'name') or ia_id
            }
        except Exception as e:
            logger.error(f"❌ Erro get_ia_stats: {e}")
            return {}
    
    def get_all_ias_stats(self):
        """Retorna stats de TODAS as IAs"""
        stats = {}
        for ia_id in self.config.get("ias", {}).keys():
            stats[ia_id] = self.get_ia_stats(ia_id)
        return stats
    
    # ═══════════════════════════════════════════════════════════════════════
    # 🔄 DETECÇÃO AUTOMÁTICA (link com parâmetro)
    # ═══════════════════════════════════════════════════════════════════════
    
    def parse_start_params(self, start_param):
        """
        Parse do parâmetro /start da URL do Telegram
        
        Exemplos:
        - /start?ia=amanda → return 'amanda'
        - /start?ia=maya_promo_123 → return 'maya'
        - /start (nada) → return default_ia
        
        Args:
            start_param: string bruto do /start (ex: 'ia=amanda')
        
        Returns:
            ia_id ou None
        """
        if not start_param:
            return None
        
        # Parse simples: "ia=amanda" ou "ia_amanda"
        if "=" in start_param:
            parts = start_param.split("=")
            if parts[0].strip().lower() in ["ia", "ia_id"]:
                ia_id = parts[1].strip().lower()
                # Sanitiza (pega apenas a parte antes de _)
                ia_id = ia_id.split("_")[0]
                if ia_id in self.config.get("ias", {}):
                    return ia_id
        
        # Tenta formato "ia_amanda"
        if start_param.lower().startswith("ia_"):
            ia_id = start_param[3:].split("_")[0].lower()
            if ia_id in self.config.get("ias", {}):
                return ia_id
        
        # Tenta formato "amanda"
        if start_param.lower() in self.config.get("ias", {}):
            return start_param.lower()
        
        return None

# ═══════════════════════════════════════════════════════════════════════════
# 🎯 EXPORT
# ═══════════════════════════════════════════════════════════════════════════

ia_router = None

def init_router(redis_url, config_path="ias_config.json"):
    """Inicializa o roteador globalmente"""
    global ia_router
    ia_router = IARouter(config_path=config_path, redis_url=redis_url)
    return ia_router

def get_router():
    """Retorna a instância global do roteador"""
    global ia_router
    if not ia_router:
        raise RuntimeError("Router não inicializado. Chame init_router() primeiro!")
    return ia_router
