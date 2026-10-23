.method public onCreate(Landroid/os/Bundle;)V
    .locals 3

    .line 1
    :try_start_0
    invoke-static {p0}, Lcom/xingin/matrix/setting/SettingActivityV2;->Sd(Lcom/xingin/matrix/setting/SettingActivityV2;)Ljava/lang/Object;
    :try_end_0
    .catchall {:try_start_0 .. :try_end_0} :catchall_0

    .line 2
    goto :goto_0

    .line 5
    :catchall_0
    move-exception v0

    .line 6
    const-string v1, "LancetHook"

    .line 7
    const-string v2, "Error in activity onCreate hook"

    .line 9
    invoke-static {v1, v2, v0}, Lxnb/d;->f(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V

    .line 11
    :goto_0
    invoke-static {p0, p1}, Lcom/xingin/matrix/setting/SettingActivityV2;->Rd(Lcom/xingin/matrix/setting/SettingActivityV2;Landroid/os/Bundle;)V

    .line 14
    return-void
    .line 17
.end method

.method public onWindowFocusChanged(Z)V
    .locals 5

    .line 1
    invoke-super {p0, p1}, Lcom/xingin/foundation/framework/v2/LCBActivity;->onWindowFocusChanged(Z)V

    .line 2
    if-eqz p1, :cond_4

    .line 5
    sget-object p1, Laa2/m;->a:Laa2/m;

    .line 7
    sget-object v0, Laa2/r0;->a:Laa2/r0;

    .line 9
    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;

    .line 11
    move-result-object v1

    .line 14
    const-string v2, " "

    .line 15
    if-eqz v1, :cond_0

    .line 17
    invoke-virtual {v1}, Landroid/content/Intent;->getExtras()Landroid/os/Bundle;

    .line 19
    move-result-object v1

    .line 22
    if-eqz v1, :cond_0

    .line 23
    const-string v3, "key_raw_url"

    .line 25
    invoke-virtual {v1, v3}, Landroid/os/BaseBundle;->getString(Ljava/lang/String;)Ljava/lang/String;

    .line 27
    move-result-object v1

    .line 30
    if-nez v1, :cond_1

    .line 31
    :cond_0
    move-object v1, v2

    .line 33
    :cond_1
    invoke-virtual {p0}, Landroid/app/Activity;->getIntent()Landroid/content/Intent;

    .line 34
    move-result-object v3

    .line 37
    if-eqz v3, :cond_3

    .line 38
    const-string v4, "sourceId"

    .line 40
    invoke-virtual {v3, v4}, Landroid/content/Intent;->getStringExtra(Ljava/lang/String;)Ljava/lang/String;

    .line 42
    move-result-object v3

    .line 45
    if-nez v3, :cond_2

    .line 46
    goto :goto_0

    .line 48
    :cond_2
    move-object v2, v3

    .line 49
    :cond_3
    :goto_0
    const-string v3, "NOTE_DETAIL_EXPOSE"

    .line 50
    invoke-virtual {v0, v1, v2, v3}, Laa2/r0;->f(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Laa2/q0;

    .line 52
    move-result-object v0

    .line 55
    invoke-virtual {p1, v0}, Laa2/m;->b(Ljava/lang/Object;)V

    .line 56
    :cond_4
    return-void
    .line 59
.end method
