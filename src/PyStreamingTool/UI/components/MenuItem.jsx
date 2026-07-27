function MenuItem({ name, icon, onClick }) {
    /* Item do menu lateral que dita o módulo do aplicativo que o usuário está vendo */
    return (
        <button className="bg-emerald-400 border-emerald-600 px-4 py-2 border rounded-2xl border-2 flex items-center gap-2 w-[60%] hover:bg-emerald-600 cursor-pointer" onClick={onClick}>
            <p >{icon}</p>
            <p className="text-white font-semibold">{name}</p>
        </button>
    );
}
