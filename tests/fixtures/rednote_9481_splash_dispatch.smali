.method public final a(Lqe/o;Lkotlin/jvm/functions/Function1;Lkotlin/jvm/functions/Function1;)V
    .locals 4
    .annotation system Ldalvik/annotation/Signature;
        value = {
            "(",
            "Lqe/o<",
            "Lcom/xingin/advert/intersitial/bean/SplashAd;",
            ">;",
            "Lkotlin/jvm/functions/Function1<",
            "-",
            "Lcom/xingin/advert/intersitial/bean/SplashAd;",
            "Lkotlin/Unit;",
            ">;",
            "Lkotlin/jvm/functions/Function1<",
            "-",
            "Ljava/lang/Integer;",
            "Lkotlin/Unit;",
            ">;)V"
        }
    .end annotation

    .line 1
    invoke-virtual {p1}, Lqe/o;->c()Z

    .line 2
    move-result v0

    .line 5
    const-string v1, "end"

    .line 6
    const-string v2, "load_end"

    .line 8
    const-string v3, "post_end"

    .line 10
    if-eqz v0, :cond_0

    .line 12
    sget-object p3, Lq50/x2;->a:Lq50/x2;

    .line 14
    invoke-virtual {p3, v3}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 16
    invoke-virtual {p3, v2}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 19
    invoke-virtual {p1}, Lqe/o;->b()Ljava/lang/Object;

    .line 22
    move-result-object p1

    .line 25
    invoke-interface {p2, p1}, Lkotlin/jvm/functions/Function1;->invoke(Ljava/lang/Object;)Ljava/lang/Object;

    .line 26
    const-string p1, "load splash ad success"

    .line 29
    invoke-static {p1}, Lc20/a;->a(Ljava/lang/String;)V

    .line 31
    sget-object p1, Lq50/t2;->a:Lq50/t2;

    .line 34
    const-string p2, "load_ad_success"

    .line 36
    invoke-virtual {p1, p2}, Lq50/t2;->a(Ljava/lang/String;)V

    .line 38
    sget-object p1, Lq50/q2;->a:Lq50/q2;

    .line 41
    invoke-virtual {p1, v1}, Lq50/q2;->d(Ljava/lang/String;)V

    .line 43
    goto :goto_0

    .line 46
    :cond_0
    sget-object p1, Lgz/f;->a:Lgz/f;

    .line 47
    invoke-virtual {p1}, Lgz/f;->a()V

    .line 49
    sget-object p1, Lq50/x2;->a:Lq50/x2;

    .line 52
    invoke-virtual {p1, v3}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 54
    invoke-virtual {p1, v2}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 57
    sget-object p1, Lq50/q2;->a:Lq50/q2;

    .line 60
    invoke-virtual {p1, v1}, Lq50/q2;->d(Ljava/lang/String;)V

    .line 62
    const/4 p1, 0x0

    .line 65
    invoke-static {p1}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    .line 66
    move-result-object p1

    .line 69
    invoke-interface {p3, p1}, Lkotlin/jvm/functions/Function1;->invoke(Ljava/lang/Object;)Ljava/lang/Object;

    .line 70
    sget-object p1, Lc20/a;->a:Lc20/a;

    .line 73
    sget-object p1, Ljuc/a;->AD_LOG:Ljuc/a;

    .line 75
    const-string p2, "AdLog"

    .line 77
    const-string p3, "no splash ad"

    .line 79
    invoke-static {p1, p2, p3}, Ljuc/f;->B(Ljuc/a;Ljava/lang/String;Ljava/lang/String;)V

    .line 81
    :goto_0
    return-void
    .line 84
.end method
