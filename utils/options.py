def get_class_options(df):
    return sorted(df["Class"].dropna().unique().tolist())

def get_topic_options(df, selected_class):
    if not selected_class:
        return []
    return sorted(
        df[df["Class"] == selected_class]["Topic"].dropna().unique().tolist()
    )

def get_question_options(df, selected_class, selected_topic):
    if not selected_class or not selected_topic:
        return []
    return sorted(
        df[
            (df["Class"] == selected_class) &
            (df["Topic"] == selected_topic)
        ]["Question"].dropna().unique().tolist()
    )
