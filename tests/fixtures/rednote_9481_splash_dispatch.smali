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

    .line 4
    move-result v0

    .line 5
    const-string v1, "end"

    .line 7
    const-string v2, "load_end"

    .line 9
    const-string v3, "post_end"

    .line 11
    if-eqz v0, :cond_0

    .line 13
    sget-object p3, Lq50/x2;->a:Lq50/x2;

    .line 15
    invoke-virtual {p3, v3}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 18
    invoke-virtual {p3, v2}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 21
    invoke-virtual {p1}, Lqe/o;->b()Ljava/lang/Object;

    .line 24
    move-result-object p1

    .line 25
    invoke-interface {p2, p1}, Lkotlin/jvm/functions/Function1;->invoke(Ljava/lang/Object;)Ljava/lang/Object;

    .line 28
    const-string p1, "load splash ad success"

    .line 30
    invoke-static {p1}, Lc20/a;->a(Ljava/lang/String;)V

    .line 33
    sget-object p1, Lq50/t2;->a:Lq50/t2;

    .line 35
    const-string p2, "load_ad_success"

    .line 37
    invoke-virtual {p1, p2}, Lq50/t2;->a(Ljava/lang/String;)V

    .line 40
    sget-object p1, Lq50/q2;->a:Lq50/q2;

    .line 42
    invoke-virtual {p1, v1}, Lq50/q2;->d(Ljava/lang/String;)V

    .line 45
    goto :goto_0

    .line 46
    :cond_0
    sget-object p1, Lgz/f;->a:Lgz/f;

    .line 48
    invoke-virtual {p1}, Lgz/f;->a()V

    .line 51
    sget-object p1, Lq50/x2;->a:Lq50/x2;

    .line 53
    invoke-virtual {p1, v3}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 56
    invoke-virtual {p1, v2}, Lq50/x2;->a(Ljava/lang/String;)V

    .line 59
    sget-object p1, Lq50/q2;->a:Lq50/q2;

    .line 61
    invoke-virtual {p1, v1}, Lq50/q2;->d(Ljava/lang/String;)V

    .line 64
    const/4 p1, 0x0

    .line 65
    invoke-static {p1}, Ljava/lang/Integer;->valueOf(I)Ljava/lang/Integer;

    .line 68
    move-result-object p1

    .line 69
    invoke-interface {p3, p1}, Lkotlin/jvm/functions/Function1;->invoke(Ljava/lang/Object;)Ljava/lang/Object;

    .line 72
    sget-object p1, Lc20/a;->a:Lc20/a;

    .line 74
    sget-object p1, Ljuc/a;->AD_LOG:Ljuc/a;

    .line 76
    const-string p2, "AdLog"

    .line 78
    const-string p3, "no splash ad"

    .line 80
    invoke-static {p1, p2, p3}, Ljuc/f;->B(Ljuc/a;Ljava/lang/String;Ljava/lang/String;)V

    .line 83
    :goto_0
    return-void
.end method
