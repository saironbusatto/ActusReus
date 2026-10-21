/*
 * mod-actus-reus: carga das tabelas actus_kit_* e aplicação do pacote num jogador online.
 */

#include "ActusReusKits.h"
#include "DBCStores.h"
#include "DatabaseEnv.h"
#include "Item.h"
#include "Log.h"
#include "Mail.h"
#include "ObjectMgr.h"
#include "Player.h"
#include "Random.h"
#include "Trainer.h"
#include <algorithm>
#include <map>
#include <sstream>
#include <tuple>

namespace ActusReus
{
    namespace
    {
        struct ItemKit
        {
            uint8 slot;
            uint32 item;
            uint32 encanto;
            uint32 gemas[4];
        };

        struct Extra
        {
            uint32 item;
            uint32 quantidade;
            bool bolsa;
        };

        enum TipoSpell : uint8
        {
            SPELL_SEMPRE = 0,
            SPELL_MONTARIA_TERRESTRE = 1,
            SPELL_MONTARIA_VOADORA = 2
        };

        struct SpellKit
        {
            uint8 classe;
            uint8 raca;
            uint32 spell;
            uint8 tipo;
        };

        constexpr uint32 MAPA_DALARAN = 571;
        constexpr uint32 AREA_DALARAN = 4395;
        constexpr float HOME_X = 5807.98f, HOME_Y = 588.49f, HOME_Z = 660.94f, HOME_O = 1.67f;
        constexpr uint32 ENCANTO_FIVELA = 3729;     // Eternal Belt Buckle: encaixe prismático no cinto
        constexpr uint32 AURA_EBON_HOLD = 51915;    // Undying Resolve, prende o DK na área inicial
        constexpr uint16 RIDING_MAXIMO = 300;
        constexpr uint8 NIVEL_FINAL = 80;

        std::map<uint8, std::vector<Spec>> _specs;
        std::map<std::tuple<uint8, uint8, uint8>, std::vector<ItemKit>> _itens;
        std::map<uint8, std::vector<Extra>> _extras;
        std::vector<SpellKit> _spells;
        std::vector<Spec> const _vazio;

        std::vector<std::string> Separar(std::string const& texto, char sep)
        {
            std::vector<std::string> partes;
            std::stringstream ss(texto);
            std::string parte;
            while (std::getline(ss, parte, sep))
                partes.push_back(parte);
            return partes;
        }

        void AprenderMagiasDeClasse(Player* player)
        {
            // igual ao ".learn all my trainer" + ".learn all my quest", sem os talentos do ".learn all my class"
            std::vector<Trainer::Trainer const*> const& treinadores = sObjectMgr->GetClassTrainers(player->getClass());
            bool aprendeuAlgo;
            do
            {
                aprendeuAlgo = false;
                for (Trainer::Trainer const* treinador : treinadores)
                {
                    if (!treinador->IsTrainerValidForPlayer(player))
                        continue;

                    for (Trainer::Spell const& magia : treinador->GetSpells())
                    {
                        if (!treinador->CanTeachSpell(player, &magia))
                            continue;

                        if (magia.IsCastable())
                            player->CastSpell(player, magia.SpellId, true);
                        else
                            player->learnSpell(magia.SpellId, false);

                        if (!treinador->CanTeachSpell(player, &magia))
                            aprendeuAlgo = true;
                    }
                }
            } while (aprendeuAlgo);

            for (auto const& par : sObjectMgr->GetQuestTemplates())
                if (par.second->GetRequiredClasses() && player->SatisfyQuestClass(par.second, false))
                    player->learnQuestRewardedSpells(par.second);
        }

        void AplicarTalentos(Player* player, std::string const& link)
        {
            player->resetTalents(true);
            std::vector<std::string> arvores = Separar(link, '-');
            for (uint32 pagina = 0; pagina < arvores.size(); ++pagina)
            {
                std::vector<TalentEntry const*> talentos;
                for (uint32 i = 0; i < sTalentStore.GetNumRows(); ++i)
                {
                    TalentEntry const* talento = sTalentStore.LookupEntry(i);
                    if (!talento)
                        continue;

                    TalentTabEntry const* aba = sTalentTabStore.LookupEntry(talento->TalentTab);
                    if (aba && (aba->ClassMask & player->getClassMask()) && aba->tabpage == pagina)
                        talentos.push_back(talento);
                }

                std::sort(talentos.begin(), talentos.end(), [](TalentEntry const* a, TalentEntry const* b)
                {
                    return std::tie(a->Row, a->Col) < std::tie(b->Row, b->Col);
                });

                std::string const& digitos = arvores[pagina];
                for (size_t i = 0; i < digitos.size() && i < talentos.size(); ++i)
                    if (uint32 pontos = digitos[i] - '0')
                        player->LearnTalent(talentos[i]->TalentID, pontos - 1);
            }
            player->SendTalentsInfoData(false);
        }

        void MandarEquipamentoAntigoPeloCorreio(Player* player)
        {
            std::vector<Item*> antigos;
            CharacterDatabaseTransaction trans = CharacterDatabase.BeginTransaction();
            for (uint8 slot = EQUIPMENT_SLOT_START; slot < EQUIPMENT_SLOT_END; ++slot)
            {
                if (slot == EQUIPMENT_SLOT_BODY || slot == EQUIPMENT_SLOT_TABARD)
                    continue;

                Item* item = player->GetItemByPos(INVENTORY_SLOT_BAG_0, slot);
                if (!item)
                    continue;

                player->MoveItemFromInventory(INVENTORY_SLOT_BAG_0, slot, true);
                item->DeleteFromInventoryDB(trans);
                item->SaveToDB(trans);
                antigos.push_back(item);
            }

            for (size_t i = 0; i < antigos.size(); i += MAX_MAIL_ITEMS)
            {
                MailDraft carta("Seu equipamento antigo", "Guardado pelo Crânio de Tyrannistrasz.");
                for (size_t j = i; j < antigos.size() && j < i + MAX_MAIL_ITEMS; ++j)
                    carta.AddItem(antigos[j]);
                carta.SendMailTo(trans, MailReceiver(player), MailSender(player, MAIL_STATIONERY_GM), MAIL_CHECK_MASK_COPIED);
            }
            CharacterDatabase.CommitTransaction(trans);
        }

        void EncaixarGemas(Item* item, ItemKit const& kit)
        {
            ItemTemplate const* proto = item->GetTemplate();
            uint32 encaixes = 0;
            for (auto const& socket : proto->Socket)
                if (socket.Color)
                    ++encaixes;

            for (uint32 i = 0; i < 4 && i < MAX_GEM_SOCKETS; ++i)
            {
                ItemTemplate const* gema = kit.gemas[i] ? sObjectMgr->GetItemTemplate(kit.gemas[i]) : nullptr;
                GemPropertiesEntry const* propriedades = gema ? sGemPropertiesStore.LookupEntry(gema->GemProperties) : nullptr;
                if (!propriedades)
                    continue;

                if (i >= encaixes)
                {
                    if (kit.slot != EQUIPMENT_SLOT_WAIST)
                        continue;
                    item->SetEnchantment(PRISMATIC_ENCHANTMENT_SLOT, ENCANTO_FIVELA, 0, 0);
                }
                item->SetEnchantment(EnchantmentSlot(SOCK_ENCHANTMENT_SLOT + i), propriedades->spellitemenchantement, 0, 0);
            }

            if (proto->socketBonus && item->GemsFitSockets())
                item->SetEnchantment(BONUS_ENCHANTMENT_SLOT, proto->socketBonus, 0, 0);
        }

        void Equipar(Player* player, std::vector<ItemKit> const& kit)
        {
            for (ItemKit const& peca : kit)
            {
                uint16 destino;
                InventoryResult resultado = player->CanEquipNewItem(peca.slot, destino, peca.item, false);
                if (resultado != EQUIP_ERR_OK)
                {
                    LOG_ERROR("module.actus", "Crânio: {} não pôde equipar item {} no slot {} (erro {})",
                        player->GetName(), peca.item, peca.slot, uint32(resultado));
                    continue;
                }

                Item* item = Item::CreateItem(peca.item, 1, player);
                if (!item)
                    continue;

                item->SetBinding(true);
                if (peca.encanto)
                    item->SetEnchantment(PERM_ENCHANTMENT_SLOT, peca.encanto, 0, 0);
                EncaixarGemas(item, peca);
                player->EquipItem(destino, item, true);
            }
            player->AutoUnequipOffhandIfNeed();
        }

        void DarExtras(Player* player)
        {
            auto const itr = _extras.find(player->getClass());
            if (itr == _extras.end())
                return;

            uint8 proximaBolsa = INVENTORY_SLOT_BAG_START;
            for (Extra const& extra : itr->second)
            {
                if (!extra.bolsa)
                    continue;

                while (proximaBolsa < INVENTORY_SLOT_BAG_END && player->GetItemByPos(INVENTORY_SLOT_BAG_0, proximaBolsa))
                    ++proximaBolsa;
                if (proximaBolsa >= INVENTORY_SLOT_BAG_END)
                    break;

                player->EquipNewItem((INVENTORY_SLOT_BAG_0 << 8) | proximaBolsa, extra.item, true);
            }

            for (Extra const& extra : itr->second)
            {
                if (extra.bolsa)
                    continue;

                if (!player->AddItem(extra.item, extra.quantidade))
                    LOG_ERROR("module.actus", "Crânio: sem espaço para {}x item {} em {}", extra.quantidade, extra.item, player->GetName());

                ItemTemplate const* proto = sObjectMgr->GetItemTemplate(extra.item);
                if (proto && proto->Class == ITEM_CLASS_PROJECTILE)
                    player->SetAmmo(extra.item);
            }
        }

        void AprenderSpellsDoKit(Player* player)
        {
            std::vector<uint32> terrestres, voadoras;
            for (SpellKit const& s : _spells)
            {
                if ((s.classe && s.classe != player->getClass()) || (s.raca && s.raca != player->getRace(true)))
                    continue;

                if (s.tipo == SPELL_MONTARIA_TERRESTRE)
                    terrestres.push_back(s.spell);
                else if (s.tipo == SPELL_MONTARIA_VOADORA)
                    voadoras.push_back(s.spell);
                else
                    player->learnSpell(s.spell, false);
            }

            for (std::vector<uint32> const* lista : { &terrestres, &voadoras })
                if (!lista->empty())
                    player->learnSpell((*lista)[urand(0, lista->size() - 1)], false);

            player->SetSkill(SKILL_RIDING, player->GetSkillStep(SKILL_RIDING), RIDING_MAXIMO, RIDING_MAXIMO);
            player->UpdateSkillsToMaxSkillsForLevel();
        }
    }

    void CarregarKits()
    {
        _specs.clear();
        _itens.clear();
        _extras.clear();
        _spells.clear();

        if (QueryResult r = WorldDatabase.Query("SELECT classe, spec, nome, papel, link_pve, link_pvp, apelidos FROM actus_kit_spec ORDER BY classe, spec"))
        {
            do
            {
                Field* f = r->Fetch();
                Spec spec;
                spec.indice = f[1].Get<uint8>();
                spec.nome = f[2].Get<std::string>();
                spec.papel = f[3].Get<std::string>();
                spec.link[MODO_PVE] = f[4].Get<std::string>();
                spec.link[MODO_PVP] = f[5].Get<std::string>();
                spec.apelidos = Separar(f[6].Get<std::string>(), ',');
                _specs[f[0].Get<uint8>()].push_back(spec);
            } while (r->NextRow());
        }

        if (QueryResult r = WorldDatabase.Query("SELECT classe, spec, modo, slot, item, encanto, gema1, gema2, gema3, gema4 FROM actus_kit_item ORDER BY slot"))
        {
            do
            {
                Field* f = r->Fetch();
                ItemKit peca{ f[3].Get<uint8>(), f[4].Get<uint32>(), f[5].Get<uint32>(),
                    { f[6].Get<uint32>(), f[7].Get<uint32>(), f[8].Get<uint32>(), f[9].Get<uint32>() } };
                _itens[{ f[0].Get<uint8>(), f[1].Get<uint8>(), f[2].Get<uint8>() }].push_back(peca);
            } while (r->NextRow());
        }

        if (QueryResult r = WorldDatabase.Query("SELECT classe, item, quantidade, e_bolsa FROM actus_kit_extra"))
        {
            do
            {
                Field* f = r->Fetch();
                _extras[f[0].Get<uint8>()].push_back({ f[1].Get<uint32>(), f[2].Get<uint32>(), f[3].Get<uint8>() != 0 });
            } while (r->NextRow());
        }

        if (QueryResult r = WorldDatabase.Query("SELECT classe, raca, spell, tipo FROM actus_kit_spell"))
        {
            do
            {
                Field* f = r->Fetch();
                _spells.push_back({ f[0].Get<uint8>(), f[1].Get<uint8>(), f[2].Get<uint32>(), f[3].Get<uint8>() });
            } while (r->NextRow());
        }

        LOG_INFO("server.loading", ">> mod-actus-reus: {} classes, {} kits, {} spells", _specs.size(), _itens.size(), _spells.size());
    }

    std::vector<Spec> const& SpecsDaClasse(uint8 classe)
    {
        auto const itr = _specs.find(classe);
        return itr != _specs.end() ? itr->second : _vazio;
    }

    Spec const* SpecPorIndice(uint8 classe, uint8 indice)
    {
        for (Spec const& spec : SpecsDaClasse(classe))
            if (spec.indice == indice)
                return &spec;
        return nullptr;
    }

    bool AplicarKit(Player* player, uint8 indiceSpec, Modo modo)
    {
        Spec const* spec = SpecPorIndice(player->getClass(), indiceSpec);
        auto const kit = _itens.find({ player->getClass(), indiceSpec, uint8(modo) });
        if (!spec || kit == _itens.end())
            return false;

        if (player->GetLevel() < NIVEL_FINAL)
            player->GiveLevel(NIVEL_FINAL);
        player->SetUInt32Value(PLAYER_XP, 0);
        player->RemoveAurasDueToSpell(AURA_EBON_HOLD);

        AprenderMagiasDeClasse(player);
        AplicarTalentos(player, spec->link[modo]);
        AprenderSpellsDoKit(player);
        MandarEquipamentoAntigoPeloCorreio(player);
        Equipar(player, kit->second);
        DarExtras(player);

        player->SetHomebind(WorldLocation(MAPA_DALARAN, HOME_X, HOME_Y, HOME_Z, HOME_O), AREA_DALARAN);
        player->SaveToDB(false, false);

        LOG_INFO("module.actus", "Crânio: {} ficou pronto como {} ({})", player->GetName(), spec->nome, modo == MODO_PVP ? "PvP" : "PvE");
        return true;
    }
}
