.class public final Let/n;
.super Ljava/lang/Object;
.source "SourceFile"


# direct methods
.method public final e(I)I
    .locals 5

    .line 1
    new-instance v0, Ljava/lang/StringBuilder;

    .line 2
    const-string v1, "currentSpanType = "

    .line 4
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 6
    invoke-virtual {p0}, Let/n;->a()I

    .line 9
    move-result v1

    .line 12
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 13
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 16
    move-result-object v0

    .line 19
    const-string v1, "DynamicColumnFitWidth"

    .line 20
    invoke-static {v1, v0}, Ljad/f;->c(Ljava/lang/String;Ljava/lang/String;)V

    .line 22
    const/4 v0, 0x1

    .line 25
    const/16 v2, 0x118

    .line 26
    if-ltz p1, :cond_0

    .line 28
    int-to-float v3, v2

    .line 30
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 31
    move-result-object v4

    .line 34
    invoke-virtual {v4}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 35
    move-result-object v4

    .line 38
    invoke-static {v0, v3, v4}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 39
    move-result v3

    .line 42
    float-to-int v3, v3

    .line 43
    if-ge p1, v3, :cond_0

    .line 44
    sget-object v2, Let/n$d;->TINNY:Let/n$d;

    .line 46
    goto/16 :goto_0

    .line 48
    :cond_0
    int-to-float v2, v2

    .line 50
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 51
    move-result-object v3

    .line 54
    invoke-virtual {v3}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 55
    move-result-object v3

    .line 58
    invoke-static {v0, v2, v3}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 59
    move-result v2

    .line 62
    float-to-int v2, v2

    .line 63
    const/16 v3, 0x1e0

    .line 64
    int-to-float v3, v3

    .line 66
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 67
    move-result-object v4

    .line 70
    invoke-virtual {v4}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 71
    move-result-object v4

    .line 74
    invoke-static {v0, v3, v4}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 75
    move-result v4

    .line 78
    float-to-int v4, v4

    .line 79
    if-gt p1, v4, :cond_1

    .line 80
    if-gt v2, p1, :cond_1

    .line 82
    sget-object v2, Let/n$d;->SMALL:Let/n$d;

    .line 84
    goto :goto_0

    .line 86
    :cond_1
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 87
    move-result-object v2

    .line 90
    invoke-virtual {v2}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 91
    move-result-object v2

    .line 94
    invoke-static {v0, v3, v2}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 95
    move-result v2

    .line 98
    float-to-int v2, v2

    .line 99
    const/16 v3, 0x2a8

    .line 100
    int-to-float v3, v3

    .line 102
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 103
    move-result-object v4

    .line 106
    invoke-virtual {v4}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 107
    move-result-object v4

    .line 110
    invoke-static {v0, v3, v4}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 111
    move-result v4

    .line 114
    float-to-int v4, v4

    .line 115
    if-gt p1, v4, :cond_2

    .line 116
    if-gt v2, p1, :cond_2

    .line 118
    sget-object v2, Let/n$d;->MIDDLE:Let/n$d;

    .line 120
    goto :goto_0

    .line 122
    :cond_2
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 123
    move-result-object v2

    .line 126
    invoke-virtual {v2}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 127
    move-result-object v2

    .line 130
    invoke-static {v0, v3, v2}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 131
    move-result v2

    .line 134
    float-to-int v2, v2

    .line 135
    const/16 v3, 0x3c0

    .line 136
    int-to-float v3, v3

    .line 138
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 139
    move-result-object v4

    .line 142
    invoke-virtual {v4}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 143
    move-result-object v4

    .line 146
    invoke-static {v0, v3, v4}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 147
    move-result v4

    .line 150
    float-to-int v4, v4

    .line 151
    if-gt p1, v4, :cond_3

    .line 152
    if-gt v2, p1, :cond_3

    .line 154
    sget-object v2, Let/n$d;->BIG:Let/n$d;

    .line 156
    goto :goto_0

    .line 158
    :cond_3
    invoke-static {}, Landroid/content/res/Resources;->getSystem()Landroid/content/res/Resources;

    .line 159
    move-result-object v2

    .line 162
    invoke-virtual {v2}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 163
    move-result-object v2

    .line 166
    invoke-static {v0, v3, v2}, Landroid/util/TypedValue;->applyDimension(IFLandroid/util/DisplayMetrics;)F

    .line 167
    move-result v2

    .line 170
    float-to-int v2, v2

    .line 171
    if-lt p1, v2, :cond_4

    .line 172
    sget-object v2, Let/n$d;->LAGE:Let/n$d;

    .line 174
    goto :goto_0

    .line 176
    :cond_4
    sget-object v2, Let/n$d;->TINNY:Let/n$d;

    .line 177
    :goto_0
    new-instance v3, Ljava/lang/StringBuilder;

    .line 179
    const-string v4, "ScreenWidth = "

    .line 181
    invoke-direct {v3, v4}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 183
    invoke-virtual {v3, p1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 186
    const-string p1, ", ScreenType = "

    .line 189
    invoke-virtual {v3, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 191
    invoke-virtual {v2}, Ljava/lang/Enum;->name()Ljava/lang/String;

    .line 194
    move-result-object p1

    .line 197
    invoke-virtual {v3, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    .line 198
    invoke-virtual {v3}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 201
    move-result-object p1

    .line 204
    invoke-static {v1, p1}, Ljad/f;->c(Ljava/lang/String;Ljava/lang/String;)V

    .line 205
    sget-object p1, Let/n$e;->a:[I

    .line 208
    invoke-virtual {v2}, Ljava/lang/Enum;->ordinal()I

    .line 210
    move-result v1

    .line 213
    aget p1, p1, v1

    .line 214
    if-eq p1, v0, :cond_f

    .line 216
    const/4 v0, 0x2

    .line 218
    if-eq p1, v0, :cond_f

    .line 219
    const/4 v1, 0x4

    .line 221
    const/4 v2, 0x3

    .line 222
    if-eq p1, v2, :cond_c

    .line 223
    if-eq p1, v1, :cond_9

    .line 225
    const/4 v0, 0x5

    .line 227
    if-ne p1, v0, :cond_8

    .line 228
    invoke-virtual {p0}, Let/n;->a()I

    .line 230
    move-result p1

    .line 233
    sget-object v3, Let/n$c;->ZOOM_OUT:Let/n$c;

    .line 234
    invoke-virtual {v3}, Ljava/lang/Enum;->ordinal()I

    .line 236
    move-result v3

    .line 239
    if-ne p1, v3, :cond_6

    .line 240
    :cond_5
    :goto_1
    const/4 v0, 0x3

    .line 242
    goto :goto_3

    .line 243
    :cond_6
    sget-object v3, Let/n$c;->NORMAL:Let/n$c;

    .line 244
    invoke-virtual {v3}, Ljava/lang/Enum;->ordinal()I

    .line 246
    move-result v3

    .line 249
    if-ne p1, v3, :cond_7

    .line 250
    :goto_2
    const/4 v0, 0x4

    .line 252
    goto :goto_3

    .line 253
    :cond_7
    sget-object v1, Let/n$c;->ZOOM_IN:Let/n$c;

    .line 254
    invoke-virtual {v1}, Ljava/lang/Enum;->ordinal()I

    .line 256
    move-result v1

    .line 259
    if-ne p1, v1, :cond_5

    .line 260
    goto :goto_3

    .line 262
    :cond_8
    new-instance p1, Lkotlin/NoWhenBranchMatchedException;

    .line 263
    invoke-direct {p1}, Lkotlin/NoWhenBranchMatchedException;-><init>()V

    .line 265
    throw p1

    .line 268
    :cond_9
    invoke-virtual {p0}, Let/n;->a()I

    .line 269
    move-result p1

    .line 272
    sget-object v3, Let/n$c;->ZOOM_OUT:Let/n$c;

    .line 273
    invoke-virtual {v3}, Ljava/lang/Enum;->ordinal()I

    .line 275
    move-result v3

    .line 278
    if-ne p1, v3, :cond_a

    .line 279
    goto :goto_3

    .line 281
    :cond_a
    sget-object v0, Let/n$c;->NORMAL:Let/n$c;

    .line 282
    invoke-virtual {v0}, Ljava/lang/Enum;->ordinal()I

    .line 284
    move-result v0

    .line 287
    if-ne p1, v0, :cond_b

    .line 288
    goto :goto_1

    .line 290
    :cond_b
    sget-object v0, Let/n$c;->ZOOM_IN:Let/n$c;

    .line 291
    invoke-virtual {v0}, Ljava/lang/Enum;->ordinal()I

    .line 293
    move-result v0

    .line 296
    if-ne p1, v0, :cond_5

    .line 297
    goto :goto_2

    .line 299
    :cond_c
    invoke-virtual {p0}, Let/n;->a()I

    .line 300
    move-result p1

    .line 303
    sget-object v3, Let/n$c;->ZOOM_OUT:Let/n$c;

    .line 304
    invoke-virtual {v3}, Ljava/lang/Enum;->ordinal()I

    .line 306
    move-result v3

    .line 309
    if-ne p1, v3, :cond_d

    .line 310
    goto :goto_3

    .line 312
    :cond_d
    sget-object v0, Let/n$c;->NORMAL:Let/n$c;

    .line 313
    invoke-virtual {v0}, Ljava/lang/Enum;->ordinal()I

    .line 315
    move-result v0

    .line 318
    if-ne p1, v0, :cond_e

    .line 319
    goto :goto_1

    .line 321
    :cond_e
    sget-object v0, Let/n$c;->ZOOM_IN:Let/n$c;

    .line 322
    invoke-virtual {v0}, Ljava/lang/Enum;->ordinal()I

    .line 324
    move-result v0

    .line 327
    if-ne p1, v0, :cond_5

    .line 328
    goto :goto_2

    .line 330
    :cond_f
    :goto_3
    return v0
    .line 331
.end method

.method public final f(Landroid/content/Context;)I
    .locals 2
    .param p1    # Landroid/content/Context;
        .annotation build Lorg/jetbrains/annotations/NotNull;
        .end annotation
    .end param

    .line 1
    sget-boolean v0, Let/n;->b:Z

    .line 2
    if-eqz v0, :cond_1

    .line 4
    sget-object v0, Let/n;->c:Lkotlin/j;

    .line 6
    check-cast v0, Lkotlin/q;

    .line 8
    invoke-virtual {v0}, Lkotlin/q;->getValue()Ljava/lang/Object;

    .line 10
    move-result-object v0

    .line 13
    check-cast v0, Ljava/lang/Boolean;

    .line 14
    invoke-virtual {v0}, Ljava/lang/Boolean;->booleanValue()Z

    .line 16
    move-result v0

    .line 19
    if-eqz v0, :cond_0

    .line 20
    invoke-static {p1}, Lcom/xingin/utils/core/r1;->f(Landroid/content/Context;)I

    .line 22
    move-result p1

    .line 25
    :goto_0
    invoke-virtual {p0, p1}, Let/n;->e(I)I

    .line 26
    move-result p1

    .line 29
    goto :goto_1

    .line 30
    :cond_0
    sget-object v0, Lcom/xingin/utils/core/r1;->a:Landroid/util/DisplayMetrics;

    .line 31
    invoke-virtual {p1}, Landroid/content/Context;->getResources()Landroid/content/res/Resources;

    .line 33
    move-result-object p1

    .line 36
    invoke-virtual {p1}, Landroid/content/res/Resources;->getDisplayMetrics()Landroid/util/DisplayMetrics;

    .line 37
    move-result-object p1

    .line 40
    iget p1, p1, Landroid/util/DisplayMetrics;->widthPixels:I

    .line 41
    goto :goto_0

    .line 43
    :cond_1
    const/4 p1, 0x2

    .line 44
    :goto_1
    new-instance v0, Ljava/lang/StringBuilder;

    .line 45
    const-string v1, "spanCount="

    .line 47
    invoke-direct {v0, v1}, Ljava/lang/StringBuilder;-><init>(Ljava/lang/String;)V

    .line 49
    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    .line 52
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    .line 55
    move-result-object v0

    .line 58
    const-string v1, "DynamicColumnFitWidth"

    .line 59
    invoke-static {v1, v0}, Ljad/f;->c(Ljava/lang/String;Ljava/lang/String;)V

    .line 61
    return p1
    .line 64
.end method
