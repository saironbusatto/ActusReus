/*
 * mod-actus-reus: kits de personagem pronto (nível 80, talentos, equipamento, montarias, bolsas e componentes).
 * Os dados vêm das tabelas actus_kit_* do acore_world, carregadas uma vez na partida do servidor.
 */

#ifndef MOD_ACTUS_REUS_KITS_H
#define MOD_ACTUS_REUS_KITS_H

#include "Define.h"
#include <string>
#include <vector>

class Player;

namespace ActusReus
{
    enum Modo : uint8
    {
        MODO_PVE = 0,
        MODO_PVP = 1
    };

    struct Spec
    {
        uint8 indice;
        std::string nome;
        std::string papel;
        std::string link[2];                // por Modo
        std::vector<std::string> apelidos;
    };

    void CarregarKits();
    std::vector<Spec> const& SpecsDaClasse(uint8 classe);
    Spec const* SpecPorIndice(uint8 classe, uint8 indice);

    // Aplica o pacote inteiro; devolve false (e não muda nada) se a spec ou o kit não existirem.
    bool AplicarKit(Player* player, uint8 indiceSpec, Modo modo);
}

#endif
