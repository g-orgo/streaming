
- Nunca altere arquivos do projeto de forma permanente sem autorização explícita. Apenas analise, explique e sugira. Todas as mudanças devem ser feitas manualmente pelo usuário, com exceção de quando o próprio usuário solicitar que o agente as faça.

- Padrão obrigatório para toda correção/diagnóstico ("testar, validar, apagar e instruir"):
  1. Quando o usuário apontar que algo não funciona (ou pedir para validar uma solução), altere os arquivos e implemente a solução candidata.
  2. Valide a solução de forma concreta: rode os testes, o `debug.bat` quando existir, o `mypy --strict`, e reproduza o problema até confirmar que a solução X resolve de fato (repita a validação o suficiente para ter confiança, ex.: 3 execuções limpas).
  3. Ao confirmar, apague **somente o que você adicionou/alterou para testar**: remova arquivos novos (ex.: scripts de teste), reverte os arquivos alterados ao estado anterior (use `git restore` quando o estado original estiver commitado; caso contrário, reverte manualmente apenas as suas mudanças). **Nunca** limpe a worktree nem reverte alterações que já existiam antes de você começar.
  4. Depois de deixar o projeto exatamente como estava, instrua o usuário com acertividade: explique o que testou, o resultado da validação e apresente as mudanças em blocos de código para ele aplicar manualmente.

- Todo código que for gerado deve ser comentado como o restante da aplicação.
