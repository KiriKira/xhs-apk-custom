.method public onBindViewHolder(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;ILjava/util/List;)V
    .locals 4
    .param p1    # Landroidx/recyclerview/widget/RecyclerView$ViewHolder;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .param p3    # Ljava/util/List;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Landroidx/recyclerview/widget/RecyclerView$ViewHolder;",
            "I",
            "Ljava/util/List<",
            "+",
            "Ljava/lang/Object;",
            ">;)V"
        }
    .end annotation

    .line 1
    iget-boolean v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->f:Z

    .line 2
    if-eqz v0, :cond_0

    .line 4
    new-instance v0, Ljava/lang/StringBuilder;

    .line 6
    const-string v1, "onBindViewHolder() position: "

    .line 8
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 10
    invoke-virtual {v0, p2}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 13
    const-string v1, "; payloads="

    .line 16
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 18
    invoke-virtual {v0, p3}, Ljava/lang/StringBuilder;->append(Ljava/lang/Object;)Ljava/lang/StringBuilder;

    .line 21
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 24
    move-result-object v0

    .line 27
    const-string v1, "FeedCustomMultiTypeAdapter"

    .line 28
    invoke-static {v1, v0}, Ljuc/f;->p(Ljava/lang/String;Ljava/lang/String;)V

    .line 30
    :cond_0
    iget-wide v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 33
    const-wide/16 v2, 0x1

    .line 35
    add-long/2addr v0, v2

    .line 37
    iput-wide v0, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 38
    invoke-super {p0, p1, p2, p3}, Lcom/drakeet/multitype/MultiTypeAdapter;->onBindViewHolder(Landroidx/recyclerview/widget/RecyclerView$ViewHolder;ILjava/util/List;)V

    .line 40
    iget-object p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->g:Lkotlin/Lazy;

    .line 43
    invoke-interface {p1}, Lkotlin/Lazy;->getValue()Ljava/lang/Object;

    .line 45
    move-result-object p1

    .line 48
    check-cast p1, Ljava/lang/Boolean;

    .line 49
    invoke-virtual {p1}, Ljava/lang/Boolean;->booleanValue()Z

    .line 51
    move-result p1

    .line 54
    if-eqz p1, :cond_1

    .line 55
    iget-wide p1, p0, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->e:J

    .line 57
    const-wide/16 v0, 0x64

    .line 59
    cmp-long p3, p1, v0

    .line 61
    if-lez p3, :cond_1

    .line 63
    const-string p1, "MAX_COUNT"

    .line 65
    invoke-virtual {p0, p1}, Lcom/xingin/xhs/homepage/explorefeed/mainfeed/view/FeedCustomMultiTypeAdapter;->M0(Ljava/lang/String;)V

    .line 67
    :cond_1
    return-void
    .line 70
.end method