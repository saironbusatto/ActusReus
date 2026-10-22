// Paridade C++/torch da política v2: lê os pesos como o servidor (ArenaMlNet.h) e, para cada linha de 151
// números na entrada, imprime as probabilidades. Compilado e comparado por train_v2.py --selftest.
#include <iostream>
#include <sstream>

#include "ArenaMlNet.h"

int main(int argc, char** argv)
{
    if (argc != 2)
        return 2;
    ai::arena::PolicyNetV2 const net(argv[1]);
    if (!net.ok)
        return 1;
    std::string line;
    while (std::getline(std::cin, line))
    {
        std::stringstream ss(line);
        std::vector<float> x;
        for (float v; ss >> v;)
            x.push_back(v);
        if (x.size() != net.InputSize())
            return 3;
        for (float p : net.Probabilities(x))
            std::cout << p << ' ';
        std::cout << '\n';
    }
    return 0;
}
