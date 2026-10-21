/*
 * mod-actus-reus: o Crânio de Tyrannistrasz, em Dalaran. Clique abre o menu (spec -> PvE/PvP -> confirmar);
 * dizer "quero jogar de <spec>" perto dele abre direto a confirmação.
 */

#include "ActusReusKits.h"
#include "Chat.h"
#include "GameObject.h"
#include "GameObjectScript.h"
#include "Player.h"
#include "PlayerScript.h"
#include "ScriptedGossip.h"
#include "WorldPacket.h"
#include "WorldScript.h"
#include <algorithm>
#include <cctype>

using namespace ActusReus;

namespace
{
    constexpr uint32 GO_CRANIO = 920000;
    constexpr float ALCANCE_DA_VOZ = 20.0f;

    enum TextoCranio : uint32
    {
        TEXTO_SAUDACAO = 920000,
        TEXTO_MODO = 920001,
        TEXTO_CONFIRMAR = 920002
    };

    enum PassoMenu : uint32
    {
        PASSO_SPEC = 100,       // ação = índice da spec
        PASSO_MODO = 101,       // ação = spec * 10 + modo
        PASSO_CONFIRMAR = 102,  // ação = spec * 10 + modo
        PASSO_DESISTIR = 103
    };

    uint32 Acao(uint8 spec, Modo modo) { return spec * 10 + modo; }

    void Sussurrar(GameObject* cranio, Player* player, std::string const& texto)
    {
        WorldPacket data;
        ChatHandler::BuildChatPacket(data, CHAT_MSG_MONSTER_WHISPER, LANG_UNIVERSAL, cranio, player, texto);
        player->SendDirectMessage(&data);
    }

    void MenuSpecs(Player* player, GameObject* cranio)
    {
        ClearGossipMenuFor(player);
        for (Spec const& spec : SpecsDaClasse(player->getClass()))
            AddGossipItemFor(player, GOSSIP_ICON_TRAINER, spec.nome, PASSO_SPEC, spec.indice);
        SendGossipMenuFor(player, TEXTO_SAUDACAO, cranio->GetGUID());
    }

    void MenuModo(Player* player, GameObject* cranio, uint8 spec)
    {
        ClearGossipMenuFor(player);
        AddGossipItemFor(player, GOSSIP_ICON_BATTLE, "PvE: dungeons e raides", PASSO_MODO, Acao(spec, MODO_PVE));
        AddGossipItemFor(player, GOSSIP_ICON_BATTLE, "PvP: arenas e campos de batalha", PASSO_MODO, Acao(spec, MODO_PVP));
        SendGossipMenuFor(player, TEXTO_MODO, cranio->GetGUID());
    }

    void MenuConfirmar(Player* player, GameObject* cranio, uint32 acao)
    {
        Spec const* spec = SpecPorIndice(player->getClass(), acao / 10);
        if (!spec)
            return;

        ClearGossipMenuFor(player);
        std::string const escolha = spec->nome + (acao % 10 == MODO_PVP ? " (PvP)" : " (PvE)");
        AddGossipItemFor(player, GOSSIP_ICON_CHAT, "Sim. Faça de mim " + escolha + ".", PASSO_CONFIRMAR, acao);
        AddGossipItemFor(player, GOSSIP_ICON_CHAT, "Ainda não.", PASSO_DESISTIR, 0);
        SendGossipMenuFor(player, TEXTO_CONFIRMAR, cranio->GetGUID());
    }

    std::string Minusculas(std::string texto)
    {
        std::transform(texto.begin(), texto.end(), texto.begin(), [](unsigned char c) { return std::tolower(c); });
        return texto;
    }
}

class go_cranio_tyrannistrasz : public GameObjectScript
{
public:
    go_cranio_tyrannistrasz() : GameObjectScript("go_cranio_tyrannistrasz") { }

    bool OnGossipHello(Player* player, GameObject* cranio) override
    {
        MenuSpecs(player, cranio);
        return true;
    }

    bool OnGossipSelect(Player* player, GameObject* cranio, uint32 passo, uint32 acao) override
    {
        switch (passo)
        {
            case PASSO_SPEC:
                MenuModo(player, cranio, acao);
                break;
            case PASSO_MODO:
                MenuConfirmar(player, cranio, acao);
                break;
            case PASSO_CONFIRMAR:
                CloseGossipMenuFor(player);
                if (player->IsInCombat())
                    Sussurrar(cranio, player, "Volte quando o sangue esfriar, mortal.");
                else if (AplicarKit(player, acao / 10, Modo(acao % 10)))
                    Sussurrar(cranio, player, "Está feito. Vá, e honre os que caíram. Seu equipamento antigo te espera no correio.");
                else
                    Sussurrar(cranio, player, "Ainda não conheço esse caminho para a sua classe.");
                break;
            default:
                CloseGossipMenuFor(player);
                break;
        }
        return true;
    }
};

class ActusReusChat : public PlayerScript
{
public:
    ActusReusChat() : PlayerScript("ActusReusChat", { PLAYERHOOK_CAN_PLAYER_USE_CHAT }) { }

    bool OnPlayerCanUseChat(Player* player, uint32 tipo, uint32 /*idioma*/, std::string& mensagem) override
    {
        if (tipo != CHAT_MSG_SAY && tipo != CHAT_MSG_YELL)
            return true;

        std::string const texto = Minusculas(mensagem);
        if (texto.find("quero jogar") == std::string::npos && texto.find("quero ser") == std::string::npos)
            return true;

        GameObject* cranio = player->FindNearestGameObject(GO_CRANIO, ALCANCE_DA_VOZ);
        if (!cranio)
            return true;

        Modo const modo = (texto.find("pvp") != std::string::npos || texto.find("arena") != std::string::npos) ? MODO_PVP : MODO_PVE;
        for (Spec const& spec : SpecsDaClasse(player->getClass()))
        {
            for (std::string const& apelido : spec.apelidos)
            {
                if (apelido.empty() || texto.find(apelido) == std::string::npos)
                    continue;

                Sussurrar(cranio, player, "Ouvi seu desejo: " + spec.nome + ". Toque em mim e confirme.");
                MenuConfirmar(player, cranio, Acao(spec.indice, modo));
                return true;
            }
        }

        Sussurrar(cranio, player, "Não reconheço esse caminho para a sua classe. Toque em mim e escolha.");
        return true;
    }
};

class ActusReusCarga : public WorldScript
{
public:
    ActusReusCarga() : WorldScript("ActusReusCarga", { WORLDHOOK_ON_STARTUP }) { }

    void OnStartup() override
    {
        CarregarKits();
    }
};

void AddActusReusScripts()
{
    new go_cranio_tyrannistrasz();
    new ActusReusChat();
    new ActusReusCarga();
}
