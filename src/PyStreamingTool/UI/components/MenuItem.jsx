function MenuItem({ name, icon, onClick }) {
    /* Item do menu lateral que dita o módulo do aplicativo que o usuário está vendo */
    return (
        <button className="bg-emerald-400 px-4 border rounded-2xl border-2 flex gap-2" onClick={onClick}>
            <p>{icon}</p>
            <p>{name}</p>
        </button>
    );
}
