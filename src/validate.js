// Shared by the card configurations: Lovelace surfaces the thrown message in
// the card editor, prefixed with the card type so the culprit is obvious.
export function configValidator(cardType) {
    function invalid(message) {
        throw new Error(`${cardType}: ${message}`);
    }

    return {
        invalid,

        integer(value, name, min, max) {
            const number = Number(value);
            if (!Number.isInteger(number) || number < min || number > max) {
                invalid(`"${name}" doit être un entier entre ${min} et ${max}`);
            }
            return number;
        },

        boolean(value, name) {
            if (typeof value !== "boolean") invalid(`"${name}" doit être vrai ou faux`);
            return value;
        },

        // Merge the defaults and check the options every card has.
        base(config, defaults) {
            if (config && typeof config !== "object") invalid("configuration invalide");
            const raw = { ...defaults, ...(config || {}) };
            if (typeof raw.entity !== "string") invalid('"entity" doit être une entité');
            if (typeof raw.title !== "string") invalid('"title" doit être du texte');
            return raw;
        },
    };
}
