function ChangelogCard() {
  return (
    <div className="relative mt-4 flex w-full flex-row items-center gap-4 rounded-md border border-muted-foreground/20 bg-muted-foreground/5 p-4 text-xs">
      <div className="flex flex-col gap-1">
        <h1 className="text-sm font-semibold">
          Neue Parteien & Chatverläufe speichern 🚀🎉
        </h1>
        <p className="text-muted-foreground">
          Du kannst dich jetzt bei uns anmelden um deine Chatverläufe zu
          speichern. Außerdem kannst du nun auch mit der <b>ÖDP</b> und der{' '}
          <b>Tierschutzpartei</b> chatten.
        </p>
      </div>
    </div>
  );
}

export default ChangelogCard;
