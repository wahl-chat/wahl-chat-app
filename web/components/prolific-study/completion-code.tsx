import {useCallback, useEffect, useState} from "react";
import {toast} from "sonner";
import {Button} from "@/components/ui/button";
import {Check, Copy} from "lucide-react";
import {getProlificCompletionCode} from "@/lib/prolific-study/prolific-server";
import {clearProlificMetadata} from "@/lib/prolific-study/prolific-metadata";

function CompletionCode() {
    const [completionCode, setCompletionCode] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
            getProlificCompletionCode().then(setCompletionCode);
    }, []);

    useEffect(() => {
        clearProlificMetadata();
    }, []);

    const handleCopy = useCallback(async () => {
        if (!completionCode) return;
        await navigator.clipboard.writeText(completionCode);
        setCopied(true);
        toast.success('Code in die Zwischenablage kopiert!');
        setTimeout(() => setCopied(false), 2000);
    }, [completionCode]);

    return (
        <>
            <div className="rounded-lg border-2 border-green-500 bg-green-50 p-4 dark:bg-green-950">
                <h2 className="text-lg font-bold text-green-800 dark:text-green-200">
                    Danke für deine Teilnahme!
                </h2>
                <p className="mt-1 text-sm text-green-700 dark:text-green-300">
                    Bitte kopiere den folgenden Code, um mit der Studie auf Prolific fortzufahren:
                </p>
                <div className="mt-3 flex items-center gap-2">
                    <code
                        className="flex-1 rounded-md bg-white px-4 py-2 font-mono text-lg font-bold text-green-900 dark:bg-green-900 dark:text-green-100">
                        {completionCode ??  "Could not fetch completion code."}
                    </code>
                    <Button
                        variant="outline"
                        size="icon"
                        onClick={handleCopy}
                        disabled={!completionCode}
                    >
                        {copied ? (
                            <Check className="size-4 text-green-600"/>
                        ) : (
                            <Copy className="size-4"/>
                        )}
                    </Button>
                </div>
            </div>
        </>
    );
}
export default CompletionCode;